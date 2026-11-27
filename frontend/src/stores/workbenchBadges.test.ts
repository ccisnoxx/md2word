import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it } from "vitest";

import {
  syncIncidentsBadgeCount,
  syncTermProposalsBadgeCount,
  syncTranslationQaBadgeCount,
  useWorkbenchBadgesStore,
} from "@/stores/workbenchBadges";

describe("workbench badges store", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
  });

  it("formats positive counts, caps values above 99, hides zero/null, and resets on logout", () => {
    const store = useWorkbenchBadgesStore();
    expect(store.navBadges).toEqual({});

    syncIncidentsBadgeCount(4);
    syncTranslationQaBadgeCount(120);
    syncTermProposalsBadgeCount(0);

    expect(store.navBadges).toEqual({
      incidents: { badge: "4", tone: "danger" },
      "translation-qa": { badge: "99+", tone: "warning" },
    });

    syncTermProposalsBadgeCount(3);
    expect(store.navBadges["term-proposals"]).toEqual({ badge: "3", tone: "warning" });

    store.reset();
    expect(store.navBadges).toEqual({});
  });
});
