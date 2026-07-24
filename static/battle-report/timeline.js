import {
  controlButton,
  cooldownNames,
  detailLine,
  effectNames,
  formatNumber,
  fraction,
  namedValues,
  names,
  node,
  rawBlock,
  renderFacts,
} from "./ui.js?v=16";

export const FILTER_OPTIONS = [
  { id: "all", label: "全部" },
  { id: "damage", label: "伤害" },
  { id: "status", label: "状态与控制" },
  { id: "resource", label: "资源与恢复" },
  { id: "system", label: "过程" },
];

export function renderCompactTimeline(segment) {
  const section = node("section", "mode-panel compact-panel");
  section.append(renderTimelineHeading("战斗记录"));
  const timeline = node("div", "timeline compact-timeline");
  if (!segment.timeline.length) {
    timeline.append(node("p", "empty-state", "本片段没有可展示的行动事实。"));
  }
  let previousRound = null;
  segment.timeline.forEach((entry, index) => {
    const round = timelineRound(entry);
    if (round && round !== previousRound) {
      timeline.append(node("div", "round-heading", `第 ${round} 回合`));
      previousRound = round;
    }
    timeline.append(renderCompactEntry(entry, index));
  });
  section.append(timeline);
  return section;
}

export function renderDetailedTimeline(segment, filter) {
  const section = node("section", "mode-panel detail-panel");
  const events = flattenEvents(segment.timeline);
  section.append(renderTimelineHeading("全部事件"));
  section.append(
    node(
      "div",
      "event-filters",
      FILTER_OPTIONS.map((option) => {
        const count = option.id === "all"
          ? events.length
          : events.filter((event) => toneCategory(event.tone) === option.id).length;
        return controlButton(
          `${option.label} ${count}`,
          "filter",
          option.id,
          filter === option.id,
        );
      }),
    ),
  );
  section.append(renderDetailedTimelineEntries(segment, filter));
  return section;
}

export function renderDetailedTimelineEntries(segment, filter) {
  const timeline = node("div", "timeline detailed-timeline region-update");
  const entries = segment.timeline
    .map((entry, index) => normalizeTimelineEntry(entry, index))
    .filter(
      (entry) => filter === "all"
        || entry.events.some((event) => toneCategory(event.tone) === filter),
    );
  if (!entries.length) {
    timeline.append(node("p", "empty-state", "当前筛选下没有事件。"));
  }
  entries.forEach((entry, index) => timeline.append(renderDetailedEntry(entry, index, filter)));
  return timeline;
}

export function renderRawDataAccess(segment) {
  const details = node("details", "raw-report-details");
  details.append(node("summary", "", "原始数据"));
  details.addEventListener("toggle", () => {
    if (!details.open || details.dataset.loaded === "true") {
      return;
    }
    details.dataset.loaded = "true";
    details.append(rawBlock(segment));
  });
  return details;
}

function renderCompactEntry(entry, index) {
  const transition = normalizeTimelineEntry(entry, index);
  const visibleEvents = transition.events.filter(isBattleRecordEvent);
  const processEvents = transition.events.filter((event) => !isBattleRecordEvent(event));
  const article = node("article", `action-card ${dominantActionClass(transition.events)}`);
  article.append(node("div", "action-head", [node("div", "action-title", transition.title)]));
  if (visibleEvents.length) {
    const events = node("ol", "event-list compact-event-list");
    visibleEvents.forEach((event) => events.append(renderEvent(event, false)));
    article.append(events);
  }
  if (processEvents.length) {
    article.append(renderEventGroup("过程记录", processEvents));
  }
  if (transition.before || transition.after) {
    article.append(renderFrameComparison(transition.before, transition.after));
  }
  return article;
}

function renderDetailedEntry(transition, index, filter) {
  const article = node("article", "action-card detailed-action");
  article.append(
    node("div", "action-head", [
      node("div", "action-title", transition.title),
      node("div", "action-sequence", transitionSequence(transition, index)),
    ]),
  );
  if (transition.facts.length) {
    article.append(renderFacts(transition.facts, "fact-row"));
  }
  const eventList = node("ol", "event-list");
  transition.events
    .filter((event) => filter === "all" || toneCategory(event.tone) === filter)
    .forEach((event) => eventList.append(renderEvent(event)));
  article.append(eventList);
  if (transition.before || transition.after) {
    article.append(renderFrameComparison(transition.before, transition.after));
  }
  return article;
}

function renderEvent(event, includeRaw = true) {
  const category = toneCategory(event.tone);
  const item = node("li", "event");
  item.dataset.tone = event.tone || "neutral";
  item.dataset.category = category;
  item.append(
    node("div", "event-heading", [
      node("span", `event-marker ${category}`, ""),
      includeRaw ? node("span", "event-label", event.label) : null,
      node("span", "event-text", event.text),
    ]),
  );
  if (includeRaw && event.facts.length) {
    item.append(
      node(
        "div",
        "event-facts",
        event.facts.map((fact) => `${fact.label}: ${fact.display}`).join(" · "),
      ),
    );
  }
  if (includeRaw) {
    const raw = node("details", "raw-details");
    raw.append(node("summary", "", event.registered ? "事件事实" : "未注册事件原始事实"));
    raw.append(rawBlock(event.raw));
    item.append(raw);
  }
  return item;
}

function renderEventGroup(title, events) {
  const details = node("details", "event-group");
  details.append(node("summary", "", `${title} · ${events.length}`));
  const list = node("ol", "event-list");
  events.forEach((event) => list.append(renderEvent(event, false)));
  details.append(list);
  return details;
}

function renderFrameComparison(before, after) {
  const details = node("details", "frame-comparison");
  details.append(node("summary", "", "行动前后状态"));
  if (before && after) {
    details.append(renderStateChanges(before.participants, after.participants));
  }
  const grid = node("div", "frame-grid");
  if (before) {
    grid.append(renderFrame(before));
  }
  if (after) {
    grid.append(renderFrame(after));
  }
  details.append(grid);
  return details;
}

function renderStateChanges(beforeParticipants, afterParticipants) {
  const beforeMap = new Map(beforeParticipants.map((item) => [item.key, item]));
  const rows = [];
  afterParticipants.forEach((after) => {
    const before = beforeMap.get(after.key);
    if (!before) {
      rows.push(`${after.label} 加入战场`);
      return;
    }
    const changes = [
      vitalChange(before.health, after.health, "血气"),
      vitalChange(before.spirit, after.spirit, "灵力"),
      effectsChange(before.effects, after.effects),
    ].filter(Boolean);
    if (changes.length) {
      rows.push(`${after.label}：${changes.join("；")}`);
    }
  });
  beforeParticipants.forEach((before) => {
    if (!afterParticipants.some((after) => after.key === before.key)) {
      rows.push(`${before.label} 离开战场`);
    }
  });
  if (!rows.length) {
    return node("p", "state-diff muted", "本次行动没有可见状态变化。");
  }
  return node("ul", "state-diff", rows.map((row) => node("li", "", row)));
}

function renderFrame(frame) {
  const article = node("article", "snapshot");
  article.append(
    node("div", "snapshot-heading", [
      node("strong", "", frame.title),
      node("span", "", `第 ${frame.round} 回合 / 行动 ${frame.turn}`),
    ]),
  );
  article.append(
    renderFacts(
      [
        { label: "状态", value: frame.status },
        { label: "行动者", value: frame.current_actor },
        { label: "顺序", value: frame.turn_order },
        { label: "失活", value: frame.inactive.length ? frame.inactive : "无" },
        { label: "胜方", value: frame.winning_teams.length ? frame.winning_teams : "未决" },
      ],
      "snapshot-facts",
    ),
  );
  article.append(
    node(
      "div",
      "snapshot-participants",
      frame.participants.map((participant) => renderSnapshotParticipant(participant)),
    ),
  );
  return article;
}

function renderSnapshotParticipant(participant) {
  const details = node("details", "participant-details");
  details.append(
    node("summary", "", [
      node("strong", "", participant.label),
      node("span", "", `血气 ${fraction(participant.health)} · 灵力 ${fraction(participant.spirit)}`),
    ]),
  );
  details.append(
    node("div", "detail-grid", [
      detailLine("属性", namedValues(participant.attributes)),
      detailLine("资源", namedValues(participant.resources)),
      detailLine("招式", names(participant.abilities)),
      detailLine("效果", effectNames(participant.effects)),
      detailLine("冷却", cooldownNames(participant.cooldowns)),
      detailLine("触发", names(participant.mechanisms.triggers)),
      detailLine("拦截", names(participant.mechanisms.interceptors)),
      detailLine("限制", names(participant.mechanisms.target_constraints)),
    ]),
  );
  return details;
}

function renderTimelineHeading(title) {
  return node("div", "timeline-heading", [node("h2", "", title)]);
}

function normalizeTimelineEntry(entry, index) {
  if (entry.type === "transition") {
    return { ...entry, facts: entry.facts || [], events: entry.events || [] };
  }
  if (entry.type === "event") {
    return {
      type: "transition",
      sequence: index + 1,
      kind: "event",
      title: entry.event?.text || entry.event?.label || "战斗事件",
      facts: [],
      events: entry.event ? [entry.event] : [],
      before: null,
      after: entry.state
        ? {
            ...entry.state,
            round: 0,
            turn: index + 1,
            status: "recorded",
            current_actor: "无",
            turn_order: [],
            inactive: [],
            winning_teams: [],
          }
        : null,
    };
  }
  return {
    type: "transition",
    sequence: index + 1,
    kind: "unknown",
    title: "未知时间线节点",
    facts: [],
    events: [],
    before: null,
    after: null,
  };
}

function toneCategory(tone) {
  if (tone === "damage") {
    return "damage";
  }
  if (["status", "control"].includes(tone)) {
    return "status";
  }
  if (["resource", "healing"].includes(tone)) {
    return "resource";
  }
  return "system";
}

function isBattleRecordEvent(event) {
  if (event.kind === "effect.applied" && Number(event.raw?.values?.stacks || 0) <= 0) {
    return false;
  }
  return ![
    "combat.battle.started",
    "combat.round.started",
    "combat.turn.started",
    "combat.turn.ended",
    "ability.started",
    "ability.completed",
    "combat.attack.hit",
    "combat.damage.dealt",
    "combat.battle.finished",
  ].includes(event.kind);
}

function dominantActionClass(events) {
  const categories = events.map((event) => toneCategory(event.tone));
  if (categories.includes("damage")) {
    return "damage-action";
  }
  if (categories.includes("status")) {
    return "status-action";
  }
  if (categories.includes("resource")) {
    return "resource-action";
  }
  return "system-action";
}

function transitionSequence(transition, index) {
  const round = timelineRound(transition);
  const parts = [`序列 ${transition.sequence ?? index + 1}`];
  if (round) {
    parts.unshift(`回合 ${round}`);
  }
  return parts.join(" · ");
}

function timelineRound(entry) {
  if (entry.after?.round) {
    return Number(entry.after.round);
  }
  const fact = (entry.facts || []).find((item) => item.label === "回合");
  return Number(fact?.value || 0);
}

function flattenEvents(timeline) {
  return timeline.flatMap((entry) => {
    if (entry.type === "transition") {
      return entry.events || [];
    }
    return entry.event ? [entry.event] : [];
  });
}

function vitalChange(before, after, label) {
  const oldValue = Number(before?.current || 0);
  const newValue = Number(after?.current || 0);
  return oldValue === newValue
    ? ""
    : `${label} ${formatNumber(oldValue)} -> ${formatNumber(newValue)}`;
}

function effectsChange(before, after) {
  const beforeNames = new Set(before.map((item) => item.name));
  const afterNames = new Set(after.map((item) => item.name));
  const added = [...afterNames].filter((name) => !beforeNames.has(name));
  const removed = [...beforeNames].filter((name) => !afterNames.has(name));
  const parts = [];
  if (added.length) {
    parts.push(`获得 ${added.join("、")}`);
  }
  if (removed.length) {
    parts.push(`失去 ${removed.join("、")}`);
  }
  return parts.join("，");
}
