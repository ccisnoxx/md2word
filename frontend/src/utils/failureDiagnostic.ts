import type { DocumentJobFailureDiagnostic, DocumentJobResponse, DocumentJobStage } from "@/api/types";
import { documentJobQualityFlagText, jobStageText } from "@/utils/format";

const reasonLabels: Record<string, string> = {
  invalid_image_asset: "图片资源无效",
  mineru_package_invalid: "解析结果包无效",
  mineru_package_limit_exceeded: "解析结果包超出处理限制",
  mineru_path_invalid: "解析结果中的文件路径不合法",
  mineru_content_list_missing: "解析结果缺少内容列表",
  mineru_json_invalid: "解析结果的 JSON 数据无效",
  mineru_content_empty: "解析结果没有可用内容",
  mineru_page_invalid: "解析结果的页面数据或页码无效",
  mineru_page_missing: "解析结果缺少页码",
  mineru_page_empty: "解析结果中有页面缺少内容",
  mineru_page_gap: "解析结果的页码不连续",
  mineru_block_invalid: "解析结果中的内容块无效",
  mineru_block_payload_invalid: "解析结果中的内容块数据无效",
  missing_table_reference: "表格引用缺失",
  invalid_table_reference: "表格引用无效",
  empty_table_html: "表格内容为空",
  invalid_table_html: "表格结构无效",
  report_limit_exceeded: "验证报告超出处理限制",
  table_render_input: "表格渲染输入无效",
  table_render_geometry: "表格行列或合并单元格的几何结构无效",
  table_render_failed: "表格渲染失败，具体原因尚未识别",
  table_build_limit: "表格规模超出处理限制",
  table_html_encoding: "表格内容编码无效",
  table_html_unsupported_structure: "表格使用了不支持的结构",
  table_placeholder_crop_failed: "表格占位图裁剪失败",
  table_placeholder_geometry_invalid: "表格占位区域无效",
  table_placeholder_integrity_failed: "表格占位完整性校验失败",
  table_placeholder_source_unavailable: "表格占位所需的源文件不可用",
};

const detailLabels: Record<string, string> = {
  unreadable_or_unsupported_image: "图片无法读取或格式不受支持",
  not_allowed_raster_format: "图片格式不在支持范围内",
  image_bytes: "图片大小超出限制",
  unreadable_archive: "结果压缩包无法读取",
  unreadable_json: "JSON 数据无法读取",
  entry_count: "压缩包文件数量超出限制",
  total_bytes: "压缩包声明的总大小超出限制",
  actual_expanded_bytes: "实际解压大小超出限制",
  single_file_bytes: "单个文件大小超出限制",
  json_bytes: "JSON 文件大小超出限制",
  nested_table: "包含嵌套表格",
  no_consumable_rows: "没有可处理的表格行",
  missing_readable_payload: "缺少可读取的内容",
  missing_readable_table_payload: "缺少可读取的表格内容",
};

const jobReasonLabels: Record<string, string> = {
  mineru_failed: "PDF 解析失败",
  document_ir_failed: "文档结构转换失败",
  render_failed: "Word 生成或质量检查失败",
  translation_failed: "翻译处理失败",
  translation_fan_in_mismatch: "翻译结果合并时内容标识不匹配",
  oss_failed: "文件或对象存储操作失败",
  document_job_invalid_input: "输入文件或任务参数无效",
  document_job_timeout: "任务处理超时",
};

const exceptionLabels: Record<string, string> = {
  ValueError: "值校验异常", KeyError: "键查找异常", TypeError: "类型异常", IndexError: "索引异常",
  AttributeError: "属性访问异常", UnicodeError: "字符编码异常", OSError: "文件或系统操作异常",
  ZeroDivisionError: "除零异常", OverflowError: "数值溢出异常", RuntimeError: "运行时异常",
};

const operationLabels: Record<string, string> = {
  section: "文档分节",
  configure_page: "页面设置",
  decoration: "页眉页脚装饰",
  block: "内容块渲染",
  image_pair: "并排图片渲染",
  column_break: "分栏换列",
  logical_table: "表格渲染",
  table_prepare: "表格预处理",
  layout_plan: "版式规划",
  table_plan: "表格规划",
  render_plan: "渲染规划",
};

function diagnosticReasonText(diagnostic: DocumentJobFailureDiagnostic): string {
  const code = diagnostic.reason_code;
  // 复用既有质量标记中文；其技术码由下方技术明细单独保留。
  const qualityText = documentJobQualityFlagText(code);
  const label = reasonLabels[code] || (qualityText !== code ? qualityText.split(" · ")[0] : null);
  const operation = diagnostic.operation_kind ? operationLabels[diagnostic.operation_kind] : null;
  const detail = diagnostic.reason ? detailLabels[diagnostic.reason] : null;
  const unknownReason = `${exceptionLabels[code] ? `${exceptionLabels[code]}（${code}）` : `诊断码 ${code}`}；具体原因尚未识别，现有诊断信息不足`;
  return [operation, label || unknownReason, detail].filter(Boolean).join("；");
}

/** 只消费后端安全投影。页码已为 1 起始，不再换算，也不从异常正文推测原因。 */
export function failureDiagnosticLines(
  diagnostic: DocumentJobFailureDiagnostic | null | undefined,
  includeTechnicalDetails = true,
): string[] {
  if (!diagnostic) {
    return ["失败位置：未记录失败页码"];
  }
  const lines = [
    `原因：${diagnosticReasonText(diagnostic)}`,
    diagnostic.scope === "page" && diagnostic.page_number !== null
      ? `首个失败位置：源 PDF 第 ${diagnostic.page_number} 页`
      : diagnostic.scope === "document"
        ? "首个失败位置：文档范围错误，无法定位单页"
        : "失败位置：未记录失败页码",
    ...(diagnostic.source_page_count
      ? [`源 PDF ${diagnostic.page_count_basis === "mineru_layout" ? "共" : "至少"} ${diagnostic.source_page_count} 页，本次未生成结果`]
      : []),
  ];
  if (diagnostic.affected_page_numbers.length) {
    lines.push(
      `受影响源页：源 PDF 第 ${diagnostic.affected_page_numbers.join("、")} 页，共 ${diagnostic.fatal_count} 个阻断问题`
        + (diagnostic.details_truncated ? "（明细已截断，列表可能不完整）" : ""),
    );
  } else if (diagnostic.details_truncated) {
    lines.push("验证明细已截断，受影响页列表可能不完整");
  }
  if (includeTechnicalDetails) {
    lines.push(`诊断原因码：${diagnostic.reason_code}${diagnostic.reason ? ` / ${diagnostic.reason}` : ""}`);
    const location = diagnostic.source === "render_operation" || diagnostic.source === "table_placeholder"
      ? [diagnostic.block_ids?.length ? `块 ${diagnostic.block_ids.join("、")}` : null,
        diagnostic.operation_kind ? `操作 ${diagnostic.operation_kind}` : null].filter(Boolean).join("，")
      : [diagnostic.source_type, diagnostic.json_pointer].filter(Boolean).join("，");
    if (location) {
      lines.push(`技术定位：${location}`);
    }
  }
  return lines;
}

type FailureSummaryJob = Pick<DocumentJobResponse,
  "status" | "stage" | "failed_stage" | "error_code" | "error_message" | "failure_diagnostic">;

/** 概览、诊断页和异常中心共用；旧任务缺少定位时仍展示已知阶段与安全任务消息。 */
export function jobFailureSummaryLines(
  job: FailureSummaryJob,
  diagnostic = job.failure_diagnostic,
  includeTechnicalDetails = false,
): string[] {
  if (job.status !== "failed") {
    return [];
  }
  const stage = job.failed_stage || diagnostic?.stage || job.stage;
  const lines = [`失败阶段：${jobStageText[stage as DocumentJobStage] || stage}`];
  if (!diagnostic) {
    const category = job.error_code ? jobReasonLabels[job.error_code] : null;
    lines.push(`原因：${category ? `${category}；` : ""}具体原因尚未识别，现有诊断信息不足`);
    if (job.error_message) {
      lines.push(`任务消息：${job.error_message}`);
    }
  }
  lines.push(...failureDiagnosticLines(diagnostic, includeTechnicalDetails));
  if (includeTechnicalDetails) {
    lines.push(`任务错误码：${job.error_code || "未记录"}`);
  }
  return lines;
}
