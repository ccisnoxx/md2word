<!-- frontend/src/components/WorkbenchPanelCard.vue: Shared card wrapper for dashboard/system workbench sections with consistent section headers. -->
<template>
  <el-card :class="cardClasses" shadow="never">
    <WorkbenchSectionHeader
      v-if="title || kicker || subtitle || $slots.actions"
      :title="title"
      :kicker="kicker"
      :subtitle="subtitle"
      :header-class="headerClass"
      :extra-class="actionsClass"
    >
      <template v-if="$slots.actions" #extra>
        <slot name="actions" />
      </template>
    </WorkbenchSectionHeader>
    <div :class="bodyClasses">
      <slot />
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { computed } from "vue";

import WorkbenchSectionHeader from "@/components/WorkbenchSectionHeader.vue";

const props = withDefaults(
  defineProps<{
    title?: string;
    kicker?: string;
    subtitle?: string;
    cardClass?: string | string[];
    headerClass?: string | string[];
    actionsClass?: string | string[];
    bodyClass?: string | string[];
  }>(),
  {
    title: "",
    kicker: "",
    subtitle: "",
    cardClass: "",
    headerClass: "",
    actionsClass: "",
    bodyClass: "",
  },
);

const cardClasses = computed(() => ["card-flat", "app-panel-card", props.cardClass]);
const bodyClasses = computed(() => ["app-panel-card-body", props.bodyClass]);
</script>

<style scoped lang="scss">
.app-panel-card-body {
  min-width: 0;
}
</style>
