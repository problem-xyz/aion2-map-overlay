import { type MessageKey, useI18n } from "@/shared/i18n";
import Icon, { type IconName } from "@/shared/ui/Icon";

import "./drop-mark.css";

const KINDS: Readonly<Record<string, { icon: IconName; label: MessageKey }>> = {
  painting: { icon: "painting", label: "timers.drop.painting" },
};

/**
 * The mark beside a world boss worth the trip for what it drops. A kind this version does not
 * know draws nothing: the list may name drops a newer app has marks for.
 */
export default function DropMark({ drops }: { drops: readonly string[] | undefined }) {
  const { t } = useI18n();
  const kind = drops?.map((d) => KINDS[d]).find(Boolean);
  if (!kind) return null;
  const label = t(kind.label);
  return (
    <span className="tm-drop" title={label}>
      <Icon name={kind.icon} />
      <span className="ui-sr-only">{label}</span>
    </span>
  );
}
