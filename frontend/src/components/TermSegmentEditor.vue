<!-- frontend/src/components/TermSegmentEditor.vue: Ordered term segment editor for proposal forms. -->
<template>
  <div class="segment-editor">
    <div class="segment-toolbar">
      <el-button size="small" @click="addSegment">新增片段</el-button>
      <el-button size="small" @click="applyVinExample">填入 VIN 示例</el-button>
      <div class="preview-box">
        <span class="muted">预览</span>
        <TermPreview :segments="modelValue" />
      </div>
    </div>

    <div v-for="(segment, index) in modelValue" :key="index" class="segment-row">
      <el-input
        :model-value="segment.segment_text"
        placeholder="片段文本"
        @update:model-value="updateSegment(index, { segment_text: String($event) })"
      />
      <el-select
        :model-value="segment.render_type"
        aria-label="片段样式"
        @update:model-value="updateSegment(index, { render_type: $event })"
      >
        <el-option label="普通" value="plain" />
        <el-option label="下标" value="subscript" />
        <el-option label="上标" value="superscript" />
      </el-select>
      <el-button-group>
        <el-button :disabled="index === 0" @click="moveSegment(index, -1)">上移</el-button>
        <el-button :disabled="index === modelValue.length - 1" @click="moveSegment(index, 1)">下移</el-button>
        <el-button type="danger" :disabled="modelValue.length === 1" @click="removeSegment(index)">删除</el-button>
      </el-button-group>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { TermRuleRenderType, TermRuleSegmentWriteRequest } from "@/api/types";
import TermPreview from "@/components/TermPreview.vue";

const props = defineProps<{
  modelValue: TermRuleSegmentWriteRequest[];
}>();

const emit = defineEmits<{
  "update:modelValue": [value: TermRuleSegmentWriteRequest[]];
}>();

function emitSegments(segments: TermRuleSegmentWriteRequest[]): void {
  emit("update:modelValue", segments);
}

function updateSegment(index: number, patch: Partial<{ segment_text: string; render_type: TermRuleRenderType }>): void {
  emitSegments(props.modelValue.map((segment, currentIndex) => (currentIndex === index ? { ...segment, ...patch } : segment)));
}

function addSegment(): void {
  emitSegments([...props.modelValue, { segment_text: "", render_type: "plain" }]);
}

function removeSegment(index: number): void {
  emitSegments(props.modelValue.filter((_, currentIndex) => currentIndex !== index));
}

function moveSegment(index: number, direction: -1 | 1): void {
  const nextIndex = index + direction;
  const segments = [...props.modelValue];
  const [segment] = segments.splice(index, 1);
  segments.splice(nextIndex, 0, segment);
  emitSegments(segments);
}

function applyVinExample(): void {
  emitSegments([
    { segment_text: "V", render_type: "plain" },
    { segment_text: "IN", render_type: "subscript" },
  ]);
}
</script>

<style scoped lang="scss">
.segment-editor {
  display: grid;
  gap: 10px;
}

.segment-toolbar {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 10px;
}

.preview-box {
  display: inline-flex;
  align-items: baseline;
  gap: 8px;
  min-height: 34px;
  padding: 4px 10px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  background: #fff;
}

.segment-row {
  display: grid;
  grid-template-columns: minmax(160px, 1fr) 140px auto;
  gap: 8px;
}

@media (max-width: 760px) {
  .segment-row {
    grid-template-columns: 1fr;
  }
}
</style>
