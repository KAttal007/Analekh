import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import { api } from "../api/client";

type Rule = { id: string; label: string; pattern: RegExp };

/** The password rules, fetched once from the server (it owns them). Until they arrive, `ready` is
 * false: nothing is listed and the forms keep their submit button off. */
export function usePasswordRules(): {
  rules: Rule[];
  maxLength: number | undefined;
  ready: boolean;
} {
  const reply = useQuery({
    queryKey: ["password-rules"],
    queryFn: api.passwordRules,
    staleTime: Infinity,
    retry: false,
  });
  const rules = useMemo(
    () => (reply.data?.rules ?? []).map((r) => ({ ...r, pattern: new RegExp(r.pattern) })),
    [reply.data],
  );
  return { rules, maxLength: reply.data?.max_length, ready: reply.data !== undefined };
}

/** A new-password box with the server's rules listed under it, each ticked as it is met. The text
 * is only ever the input's value: it is tested against the patterns here and sent nowhere. */
export function NewPasswordField({
  value,
  onChange,
  label = "New password",
  name = "new-password",
}: {
  value: string;
  onChange: (value: string) => void;
  label?: string;
  name?: string;
}) {
  const { rules, maxLength } = usePasswordRules();
  return (
    <>
      <label className="field">
        {label}
        <input
          type="password"
          name={name}
          autoComplete="new-password"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          maxLength={maxLength}
          required
        />
      </label>
      <ul className="password-rules" aria-live="polite" aria-label="Password rules">
        {rules.map((r) => {
          const met = r.pattern.test(value);
          return (
            <li key={r.id} data-met={met} className={met ? "rule-met" : undefined}>
              <span aria-hidden>{met ? "✓" : "○"}</span> {r.label}
              <span className="sr-only">{met ? " (met)" : " (not met yet)"}</span>
            </li>
          );
        })}
      </ul>
    </>
  );
}
