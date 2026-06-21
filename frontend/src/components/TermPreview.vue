<!-- frontend/src/components/TermPreview.vue: Render plain/subscript/superscript term segments. -->
<template>
  <span class="term-preview">
    <template v-for="(segment, index) in segments" :key="`${index}-${segment.render_type}-${segment.segment_text}`">
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
  display: inline-block;
  min-height: 28px;
  font-size: 18px;
  font-weight: 650;
  line-height: 1.35;
  letter-spacing: 0;
  vertical-align: baseline;
}

.term-preview sub,
.term-preview sup {
  line-height: 0;
}
</style>
