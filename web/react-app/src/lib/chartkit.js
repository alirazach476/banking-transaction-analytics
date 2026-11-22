export const axis = (t, extra = {}) => ({ axisLine: { lineStyle: { color: t.grid } }, axisTick: { show: false }, axisLabel: { color: t.muted, fontSize: 11 }, splitLine: { lineStyle: { color: t.grid } }, ...extra });
export const baseGrid = { left: 8, right: 16, top: 28, bottom: 8, containLabel: true };
