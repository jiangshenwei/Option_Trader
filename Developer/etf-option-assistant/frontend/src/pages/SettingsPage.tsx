import { useCallback, useEffect, useState } from "react";
import { api } from "../api/client";
import type { Settings } from "../types";

export default function SettingsPage() {
  const [settings, setSettings] = useState<Settings | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [nonStdHint, setNonStdHint] = useState(false);

  useEffect(() => {
    api.getSettings()
      .then((s) => setSettings({ ...s, show_non_standard: s.show_non_standard ?? false }))
      .catch((e: Error) => setError(e.message));
  }, []);

  const save = useCallback((patch: Settings) => {
    setSaving(true);
    setError(null);
    api.updateSettings(patch)
      .then((s) => setSettings({ ...s, show_non_standard: s.show_non_standard ?? false }))
      .catch((e: Error) => setError(e.message))
      .finally(() => setSaving(false));
  }, []);

  const update = (field: keyof Settings, raw: string) => {
    if (!settings) return;
    const next = { ...settings, [field]: +raw };
    setSettings(next);
    save(next);
  };

  const toggleNonStandard = (checked: boolean) => {
    if (!settings) return;
    const next = { ...settings, show_non_standard: checked };
    setSettings(next);
    setNonStdHint(true);
    save(next);
  };

  if (error && !settings) return <p className="muted">加载失败：{error}</p>;
  if (!settings) return <p className="muted">加载中…</p>;

  return (
    <>
      <p className="muted" style={{ marginTop: 0 }}>
        参数修改后自动保存；期权链报价（热力图/T 型）不自动刷新，仅进入页面或点击刷新时更新
        {saving ? " · 保存中…" : ""}
      </p>
      {error && <p className="muted" style={{ color: "var(--red)" }}>保存失败：{error}</p>}
      {nonStdHint && (
        <p className="settings-hint">
          已切换非标准合约显示，请手动刷新热力图或 T 型报价页以加载新期权链。
        </p>
      )}
      <div className="setting-row">
        <span>显示非标准合约</span>
        <div className="setting-input-wrap">
          <label className="setting-checkbox">
            <input
              type="checkbox"
              checked={settings.show_non_standard}
              onChange={(e) => toggleNonStandard(e.target.checked)}
            />
            <span>开启后在热力图/T 型中追加非标准合约的独立行权价列（默认仅标准间距列）</span>
          </label>
        </div>
      </div>
      <div className="setting-row">
        <span>无风险利率 r</span>
        <div className="setting-input-wrap">
          <input
            type="number"
            className="setting-input"
            step={0.001}
            min={0}
            max={1}
            value={settings.r}
            onChange={(e) => update("r", e.target.value)}
          />
        </div>
      </div>
      <div className="setting-row">
        <span>分红率 q</span>
        <div className="setting-input-wrap">
          <input
            type="number"
            className="setting-input"
            step={0.001}
            min={0}
            max={1}
            value={settings.q}
            onChange={(e) => update("q", e.target.value)}
          />
        </div>
      </div>
      <div className="setting-row">
        <span>行情刷新频率</span>
        <div className="setting-input-wrap">
          <input
            type="number"
            className="setting-input"
            step={1}
            min={3}
            max={300}
            value={settings.quote_refresh_sec}
            onChange={(e) => update("quote_refresh_sec", e.target.value)}
          />
          <span className="muted">秒（期权链报价不自动刷新，预留）</span>
        </div>
      </div>
      <div className="setting-row">
        <span>首页刷新频率</span>
        <div className="setting-input-wrap">
          <input
            type="number"
            className="setting-input"
            step={1}
            min={5}
            max={600}
            value={settings.home_refresh_sec}
            onChange={(e) => update("home_refresh_sec", e.target.value)}
          />
          <span className="muted">秒（首页自动刷新）</span>
        </div>
      </div>
    </>
  );
}
