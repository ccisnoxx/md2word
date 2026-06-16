<!-- frontend/src/components/TermPreview.vue: Render plain/subscript/superscript term segments. -->
<template>
  <span class="term-preview">
    <template v-for="(segment, index) in segments" :key="`${index}-${segment.render_type}`">
      <sub v-if="segment.render_type === 'subscript'">{{ segment.segment_text }}</sub>
      <sup v-else-if="segment.render_type === 'superscript'">{{ segment.segment_text }}</sup>
      <span v-else>{{ segment.segment_text }}</span>
    </template>
  </span>
</template>

<script setup lang="ts">
import type { TermRuleSegmentWriteRequest } from "@/api/types";

defineProps<{
  segments: TermRuleSegmentWriteRequest[];
}>();
</script>

<style scoped lang="scss">
.term-preview {
  display: inline-flex;
  align-items: baseline;
  min-height: 28px;
  font-size: 18px;
  font-weight: 650;
  letter-spacing: 0;
}
</style>
