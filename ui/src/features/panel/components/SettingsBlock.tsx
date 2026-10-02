import type { ReactNode } from "react";

import type { RouteView, Settings, SettingsSchema } from "@/shared/backend/contract";
import { useConfirm } from "@/shared/hooks/useConfirm";
import { available, languageName, type MessageKey, useI18n } from "@/shared/i18n";
import Icon from "@/shared/ui/Icon";
import Segmented from "@/shared/ui/Segmented";
import SettingSlider from "@/shared/ui/SettingSlider";
import Switch from "@/shared/ui/Switch";

import Card from "./Card";

/**
 * The patch callback useSettingsPatch hands out. Generic over the key, so a value is checked
 * against the type of that one setting rather than against the union of all of them.
 */
export type SettingsChange = <K extends keyof Settings>(key: K, value: Settings[K]) => void;

const ROUTE_VIEWS: readonly { value: RouteView; label: MessageKey }[] = [
  { value: "steps", label: "panel.settings.routeViewSteps" },
  { value: "dim", label: "panel.settings.routeViewDim" },
  { value: "all", label: "panel.settings.routeViewAll" },
];

export interface SettingsBlockProps {
  settings: Settings;
  /** getState's settingsSchema: where every slider here takes its range from. */
  schema: SettingsSchema | undefined;
  onChange: SettingsChange;
  /** Called once the user has confirmed; the confirmation itself happens here. */
  onReset: () => void;
  /** The checklist's card, after the route's: both are about what is drawn over the game. */
  checklist?: ReactNode;
  /** Cards between the advanced settings and the reset at the section's foot: Updates. */
  children?: ReactNode;
}

/**
 * The settings, a card per thing they are about: the app itself, the route drawn over the game,
 * and -- folded away -- how the map is followed and how it is found. Every field says what it is
 * in a word or two; the longer explanation is behind the "i" beside its label, so the cards stay
 * short enough to scan.
 */
export default function SettingsBlock({
  settings,
  schema,
  onChange,
  onReset,
  checklist = null,
  children = null,
}: SettingsBlockProps) {
  const { t, format } = useI18n();
  const confirm = useConfirm();
  const s = settings;
  return (
    <>
      <Card title={t("panel.settings.general")}>
        {/* First, because it is the only control here that changes every other label on screen.
            The options come from the catalogues that shipped, so a new locales/<code>.json shows
            up by itself -- but Settings.language in core/settings.py still lists its choices,
            and that list has to grow with it. */}
        <Segmented
          label={t("panel.settings.language")}
          value={s.language}
          options={[
            { value: "auto", label: t("panel.settings.languageAuto") },
            ...available.map((code) => ({
              value: code as Settings["language"],
              label: languageName(code),
            })),
          ]}
          tip={t("panel.settings.languageTip")}
          onChange={(v) => onChange("language", v)}
        />
        <SettingSlider
          name="fps"
          schema={schema}
          label={t("panel.settings.fps")}
          value={s.fps}
          format={(v) => t("panel.settings.fpsValue", { value: v })}
          tip={t("panel.settings.fpsTip")}
          onChange={(v) => onChange("fps", v)}
        />
      </Card>

      <Card title={t("panel.settings.overlay")}>
        <SettingSlider
          name="opacity"
          schema={schema}
          label={t("panel.settings.opacity")}
          value={s.opacity}
          format={(v) => format.percent(v)}
          tip={t("panel.settings.opacityTip")}
          onChange={(v) => onChange("opacity", v)}
        />
        <Segmented
          label={t("panel.settings.routeView")}
          value={s.route_view}
          options={ROUTE_VIEWS.map(({ value, label }) => ({ value, label: t(label) }))}
          tip={t("panel.settings.routeViewTip")}
          onChange={(v) => onChange("route_view", v)}
        />
        {/* Each count only where it changes what is drawn: "all" draws every step ahead. The steps
            passed are always offered: the steps list keeps that many, whatever the map draws */}
        {s.route_view !== "all" ? (
          <SettingSlider
            name="route_ahead"
            schema={schema}
            label={t("panel.settings.routeAhead")}
            value={s.route_ahead}
            format={(v) => format.number(v)}
            tip={t("panel.settings.routeAheadTip")}
            onChange={(v) => onChange("route_ahead", v)}
          />
        ) : null}
        <SettingSlider
          name="route_past"
          schema={schema}
          label={t("panel.settings.routePast")}
          value={s.route_past}
          format={(v) => (v === 0 ? t("panel.settings.routePastNone") : format.number(v))}
          tip={t("panel.settings.routePastTip")}
          onChange={(v) => onChange("route_past", v)}
        />
        <SettingSlider
          name="cube_radius"
          schema={schema}
          label={t("panel.settings.cubeRadius")}
          value={s.cube_radius}
          format={(v) =>
            v === 0
              ? t("panel.settings.cubeRadiusNone")
              : t("panel.settings.cubeRadiusValue", { value: format.number(v) })
          }
          tip={t("panel.settings.cubeRadiusTip")}
          onChange={(v) => onChange("cube_radius", v)}
        />
        <Switch
          checked={s.route_far_notice}
          onChange={(on) => onChange("route_far_notice", on)}
          label={t("panel.settings.farNotice")}
          hint={t("panel.settings.farNoticeHint")}
        />
      </Card>

      {checklist}

      {/* Collapsed by default: everything in here is how the map is found and followed, which
          the defaults get right for most maps, and it is the part a user can break detection
          with. A native <details> is its own disclosure widget, keyboard and screen reader
          included; its summary is the card's head. */}
      <details className="ui-frame pn-card pn-advanced">
        <summary className="pn-card-head">
          <span className="pn-advanced-title">{t("panel.settings.advanced")}</span>
          <Icon name="chevronDown" className="pn-advanced-chevron" />
        </summary>
        <div className="pn-card-rule" />
        <div className="pn-card-body">
          <p className="muted pn-card-text">{t("panel.settings.advancedHint")}</p>

          <section className="pn-subgroup" aria-labelledby="pn-settings-following">
            <h3 id="pn-settings-following" className="pn-subhead">
              {t("panel.settings.following")}
            </h3>
            <Segmented
              label={t("panel.settings.tracking")}
              value={s.tracking}
              options={[
                { value: "flow", label: t("panel.settings.trackingFlow") },
                { value: "detect", label: t("panel.settings.trackingDetect") },
              ]}
              tip={t("panel.settings.trackingTip")}
              onChange={(v) => onChange("tracking", v)}
            />
            {s.tracking === "flow" ? (
              <SettingSlider
                name="detect_interval"
                schema={schema}
                label={t("panel.settings.detectInterval")}
                value={s.detect_interval}
                // A step of 0.1 lands on values like 0.30000000000000004, and the read-out has
                // always shown one decimal: the digits are pinned here rather than left to the
                // default.
                format={(v) =>
                  t("panel.settings.detectIntervalValue", {
                    value: format.number(v, {
                      minimumFractionDigits: 1,
                      maximumFractionDigits: 1,
                    }),
                  })
                }
                tip={t("panel.settings.detectIntervalTip")}
                onChange={(v) => onChange("detect_interval", v)}
              />
            ) : null}
            <SettingSlider
              name="smoothing"
              schema={schema}
              label={t("panel.settings.smoothing")}
              value={s.smoothing}
              format={(v) => (v === 0 ? t("panel.settings.smoothingOff") : format.percent(v))}
              tip={t("panel.settings.smoothingTip")}
              onChange={(v) => onChange("smoothing", v)}
            />
            <Segmented
              label={t("panel.settings.transform")}
              value={s.transform}
              options={[
                { value: "similarity", label: t("panel.settings.transformSimilarity") },
                { value: "homography", label: t("panel.settings.transformHomography") },
              ]}
              tip={t("panel.settings.transformTip")}
              onChange={(v) => onChange("transform", v)}
            />
          </section>

          <section className="pn-subgroup" aria-labelledby="pn-settings-finding">
            <h3 id="pn-settings-finding" className="pn-subhead">
              {t("panel.settings.finding")}
            </h3>
            <Segmented
              label={t("panel.settings.detector")}
              value={s.detector}
              options={[
                { value: "sift", label: t("panel.settings.detectorSift") },
                { value: "orb", label: t("panel.settings.detectorOrb") },
              ]}
              tip={t("panel.settings.detectorTip")}
              onChange={(v) => onChange("detector", v)}
            />
            <Segmented
              label={t("panel.settings.detectScale")}
              value={s.detect_scale}
              options={[
                { value: 1, label: "100%" },
                { value: 0.75, label: "75%" },
                { value: 0.5, label: "50%" },
              ]}
              tip={t("panel.settings.detectScaleTip")}
              onChange={(v) => onChange("detect_scale", v)}
            />
            <SettingSlider
              name="min_inliers"
              schema={schema}
              label={t("panel.settings.minInliers")}
              value={s.min_inliers}
              tip={t("panel.settings.minInliersTip")}
              onChange={(v) => onChange("min_inliers", v)}
            />
          </section>
        </div>
      </details>

      {children}

      <div className="pn-section-foot">
        <button
          type="button"
          className="btn-small ghost"
          onClick={() => {
            void confirm(t("panel.settings.confirmReset"), {
              confirmLabel: t("panel.settings.reset"),
            }).then((ok) => {
              if (ok) onReset();
            });
          }}
        >
          {t("panel.settings.reset")}
        </button>
      </div>
    </>
  );
}
