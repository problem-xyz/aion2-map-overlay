import type { ReactNode } from "react";

import type { Region as RegionRect } from "@/shared/backend/contract";
import { useI18n } from "@/shared/i18n";
import Card from "@/shared/ui/Card";
import Icon from "@/shared/ui/Icon";

export interface RegionProps {
  region: RegionRect | null;
  onSelect: () => void;
  onReset: () => void;
  /** More rows of the card: the preview of what detection sees in the area. */
  children?: ReactNode;
}

/** Where on screen the game shows its map, at the head of the Settings section. */
export default function Region({ region, onSelect, onReset, children = null }: RegionProps) {
  const { t, format } = useI18n();
  return (
    <Card
      title={t("panel.region.title")}
      aside={
        <button type="button" className="btn-small ui-with-icon" onClick={onSelect}>
          <Icon name="area" />
          {region ? t("panel.region.reselect") : t("panel.region.select")}
        </button>
      }
    >
      {region ? (
        <div className="pn-area">
          <p className="pn-area-size">
            <b>
              {region.width} × {region.height}
            </b>
            <span className="muted">
              {t("panel.region.origin", {
                left: format.coordinate(region.left),
                top: format.coordinate(region.top),
              })}
            </span>
          </p>
          <button type="button" className="btn-small pn-area-reset" onClick={onReset}>
            {t("panel.region.reset")}
          </button>
        </div>
      ) : (
        <p className="muted pn-card-text">{t("panel.region.empty")}</p>
      )}
      {children}
    </Card>
  );
}
