// odds.js
const CARD_TOTAL = 43848;

const UPGRADE_EFFECTS = {
  Bronze: (s, level) => { s.w_slots += level * 1; },
  Silver: (s, level) => { s.w_boost += level * 25; },
  Gold: (s, level) => { s.kp_usage -= level * 10; },
  Sapphire: (s, level) => { s.rolls += level * 1; },
  Ruby: (s, level) => {
    if (level >= 1) s.w_slots += 2;
    if (level >= 2) s.w_boost += 50;
    if (level >= 3) s.kp_usage -= 20;
    if (level >= 4) s.rolls += 2;
  },
};

export function defaultStats() {
  return {
    rolls: 10,
    w_slots: 5,
    sw_slots: 1,
    w_boost: 0,
    sw_boost: 0,
    disabled_cards: 0,
    cards_left: CARD_TOTAL,
    cards_claimed: 0,
    kp_limit: 100,
    kp_usage: 100,
    kp_bonus: 0,
    og_server: false,
    tuto_lvl: 0,
    persrare: 1,
  };
}

function cardsAvailable(stats) {
  return stats.cards_left - stats.disabled_cards;
}

function tutoCheck(stats) {
  if (stats.tuto_lvl >= 16) {
    stats.sw_boost += 100;
  } else if (stats.tuto_lvl >= 10) {
    stats.sw_boost += 50;
  }
}

export function computeEffectiveStats(baseStats, upgrades) {
  const stats = { ...baseStats };

  Object.entries(upgrades || {}).forEach(([name, level]) => {
    const nLevel = Number(level) || 0;
    if (nLevel > 0 && UPGRADE_EFFECTS[name]) {
      UPGRADE_EFFECTS[name](stats, nLevel);
    }
  });

  if (stats.og_server) {
    stats.rolls += 3;
  }

  tutoCheck(stats);
  stats.cards_claimed = CARD_TOTAL - stats.cards_left;
  return stats;
}

export function calculateOdds(stats) {
  const available = cardsAvailable(stats);
  if (available <= 0) {
    return {
      specific_roll_odds: 0,
      specific_wish_odds: 0,
      wish_odds: 0,
      star_wish_odds: 0,
      kspawn_odds: 0,
    };
  }

  const base = 1 / available;
  const wishMult = 1 + stats.w_boost / 100;
  const starMult = 1 + (stats.w_boost + stats.sw_boost) / 100;

  const specific_roll_odds = base;
  const specific_wish_odds = base * wishMult;

  const normalSlots = Math.max(0, stats.w_slots - stats.sw_slots);
  const wish_odds = normalSlots * base * wishMult;

  const star_wish_odds = stats.sw_slots * base * starMult;

  const kRaw = (stats.cards_claimed * (50 / Math.max(1, stats.persrare))) / available;
  const kspawn_odds = Math.max(0, Math.min(1, kRaw));

  return { specific_roll_odds, specific_wish_odds, wish_odds, star_wish_odds, kspawn_odds };
}

// Helper for forms: pass field values as strings/numbers/booleans
export function calculateFromInputs(inputs) {
  const base = defaultStats();
  Object.assign(base, inputs);
  base.disabled_cards = Number(base.disabled_cards || 0);
  base.cards_left = Number(base.cards_left || CARD_TOTAL);
  base.tuto_lvl = Number(base.tuto_lvl || 0);
  base.persrare = Number(base.persrare || 1);
  base.og_server = Boolean(base.og_server);
  return calculateOdds(computeEffectiveStats(base, inputs.upgrades || {}));
}
