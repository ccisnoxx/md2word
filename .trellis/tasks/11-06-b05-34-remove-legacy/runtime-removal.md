# 旧转换运行时删除记录

## 保留边界

`app/conversion/docx_rules/*`、`app/conversion/runtime/table_html_parser.py` 及三个包初始化文件保留原样。表格解析器仅依赖标准库；正式 DocumentIR 和 renderer 通过这些文件复用纯规则。正式 IR/renderer 源码未修改。

## 删除源码

- `app/conversion/contracts.py`：66 行；仅旧 stage 转换链使用。
- `app/conversion/entrypoint.py`：79 行；仅旧 stage 转换链使用。
- `app/conversion/runtime/input_adapter_runtime.py`：1095 行；仅旧 stage 转换链使用。
- `app/conversion/runtime/llm_client.py`：162 行；仅旧 stage 转换链使用。
- `app/conversion/runtime/page_flow_runtime.py`：359 行；仅旧 stage 转换链使用。
- `app/conversion/runtime/page_layout_runtime.py`：1144 行；仅旧 stage 转换链使用。
- `app/conversion/runtime/page_repair_runtime.py`：179 行；仅旧 stage 转换链使用。
- `app/conversion/runtime/render_config_runtime.py`：214 行；仅旧 stage 转换链使用。
- `app/conversion/runtime/table_long_renderer.py`：362 行；仅旧 stage 转换链使用。
- `app/conversion/runtime/table_render_runtime.py`：367 行；仅旧 stage 转换链使用。
- `app/conversion/runtime/text_rendering.py`：713 行；仅旧 stage 转换链使用。
- `app/conversion/runtime/translation_runtime.py`：690 行；仅旧 stage 转换链使用。
- `app/conversion/runtime_config.py`：11 行；仅旧 stage 转换链使用。
- `app/conversion/runtime_facade.py`：28 行；仅旧 stage 转换链使用。
- `app/conversion/runtime_helpers.py`：207 行；仅旧 stage 转换链使用。
- `app/conversion/runtime_models.py`：122 行；仅旧 stage 转换链使用。
- `app/conversion/runtime_rendering_api.py`：361 行；仅旧 stage 转换链使用。
- `app/conversion/runtime_runner.py`：274 行；仅旧 stage 转换链使用。
- `app/conversion/service.py`：113 行；仅旧 stage 转换链使用。

旧 contracts 的 app/api/errors.py 调用由 jobs 分工同步移除；stage 与 main 装配由主会话协调处理。

## 删除专属测试

- `tests/test_llm_client_characterization.py`：113 行，6 个测试。只测旧 llm_client 的客户端创建、旧 payload 与系统提示读取，正式 Provider 无调用。
  - `test_build_client_requires_sdk`：只测旧 llm_client 的客户端创建、旧 payload 与系统提示读取，正式 Provider 无调用。
  - `test_build_client_requires_api_key`：只测旧 llm_client 的客户端创建、旧 payload 与系统提示读取，正式 Provider 无调用。
  - `test_translate_payload_uses_chat_completion_items`：只测旧 llm_client 的客户端创建、旧 payload 与系统提示读取，正式 Provider 无调用。
  - `test_parse_json_response_accepts_code_fence`：只测旧 llm_client 的客户端创建、旧 payload 与系统提示读取，正式 Provider 无调用。
  - `test_build_system_prompt_reads_template_file`：只测旧 llm_client 的客户端创建、旧 payload 与系统提示读取，正式 Provider 无调用。
  - `test_build_system_prompt_selects_ru2zh_template`：只测旧 llm_client 的客户端创建、旧 payload 与系统提示读取，正式 Provider 无调用。
- `tests/test_page_repair_characterization.py`：131 行，6 个测试。只测旧 PageData/MiddlePage 的版面修复与旧 load_pages。
  - `test_bbox_distance_sums_coordinate_deltas`：只测旧 PageData/MiddlePage 的版面修复与旧 load_pages。
  - `test_find_best_visual_match_picks_closest_same_type_under_threshold`：只测旧 PageData/MiddlePage 的版面修复与旧 load_pages。
  - `test_find_best_visual_match_returns_none_when_distance_too_large`：只测旧 PageData/MiddlePage 的版面修复与旧 load_pages。
  - `test_merge_page_with_middle_backfills_header_and_visual_metadata`：只测旧 PageData/MiddlePage 的版面修复与旧 load_pages。
  - `test_attach_table_continuations_moves_placeholder_heights_to_last_real_table`：只测旧 PageData/MiddlePage 的版面修复与旧 load_pages。
  - `test_load_pages_merges_middle_sorts_blocks_and_attaches_continuations`：只测旧 PageData/MiddlePage 的版面修复与旧 load_pages。
- `tests/test_page_layout_characterization.py`：635 行，27 个测试。只测旧 PageData、动态绑定的页面分节与 build_document writer。
  - `test_split_page_blocks_separates_header_footer_page_number_and_body`：只测旧 PageData、动态绑定的页面分节与 build_document writer。
  - `test_configure_section_uses_default_word_page_size_not_source_pdf_page_size`：只测旧 PageData、动态绑定的页面分节与 build_document writer。
  - `test_configure_section_prefers_yaml_page_size_over_source_pdf_page_size`：只测旧 PageData、动态绑定的页面分节与 build_document writer。
  - `test_is_toc_page_true_for_explicit_directory_title`：只测旧 PageData、动态绑定的页面分节与 build_document writer。
  - `test_is_toc_page_true_for_english_contents_title`：只测旧 PageData、动态绑定的页面分节与 build_document writer。
  - `test_is_toc_continuation_page_true_for_toc_like_list_page`：只测旧 PageData、动态绑定的页面分节与 build_document writer。
  - `test_build_regions_detects_two_col_band_then_one_col_region`：只测旧 PageData、动态绑定的页面分节与 build_document writer。
  - `test_build_regions_keeps_separated_source_columns_in_one_two_col_region`：只测旧 PageData、动态绑定的页面分节与 build_document writer。
  - `test_split_toc_page_blocks_separates_later_body_title`：只测旧 PageData、动态绑定的页面分节与 build_document writer。
  - `test_split_toc_column_blocks_uses_source_left_and_right_toc_columns`：只测旧 PageData、动态绑定的页面分节与 build_document writer。
  - `test_split_toc_column_blocks_rejects_single_column_toc`：只测旧 PageData、动态绑定的页面分节与 build_document writer。
  - `test_render_document_page_body_renders_mixed_toc_remainder_as_body`：只测旧 PageData、动态绑定的页面分节与 build_document writer。
  - `test_render_page_body_skips_primary_product_title_when_requested`：只测旧 PageData、动态绑定的页面分节与 build_document writer。
  - `test_render_page_body_applies_flow_plan_break_before_region`：只测旧 PageData、动态绑定的页面分节与 build_document writer。
  - `test_render_block_into_container_disables_keep_with_next_before_visual_block`：只测旧 PageData、动态绑定的页面分节与 build_document writer。
  - `test_render_block_into_container_promotes_bullet_like_paragraph_to_list`：只测旧 PageData、动态绑定的页面分节与 build_document writer。
  - `test_should_start_new_section_false_for_consecutive_normal_pages`：只测旧 PageData、动态绑定的页面分节与 build_document writer。
  - `test_should_start_new_section_ignores_source_orientation_when_word_page_size_is_configured`：只测旧 PageData、动态绑定的页面分节与 build_document writer。
  - `test_should_start_new_section_true_when_leaving_toc`：只测旧 PageData、动态绑定的页面分节与 build_document writer。
  - `test_should_start_new_section_false_for_appendix_entry_inside_toc_continuation`：只测旧 PageData、动态绑定的页面分节与 build_document writer。
  - `test_should_start_new_section_true_for_appendix_title_page`：只测旧 PageData、动态绑定的页面分节与 build_document writer。
  - `test_should_start_new_section_true_for_english_appendix_title_page`：只测旧 PageData、动态绑定的页面分节与 build_document writer。
  - `test_should_start_new_section_true_for_top_level_title_after_dense_visual_page`：只测旧 PageData、动态绑定的页面分节与 build_document writer。
  - `test_should_start_new_section_false_for_top_level_title_after_short_visual_page`：只测旧 PageData、动态绑定的页面分节与 build_document writer。
  - `test_should_start_new_section_false_when_previous_visual_page_already_overflows`：只测旧 PageData、动态绑定的页面分节与 build_document writer。
  - `test_build_document_reuses_single_section_for_same_orientation_flow_pages`：只测旧 PageData、动态绑定的页面分节与 build_document writer。
  - `test_build_document_skips_empty_page_and_keeps_toc_continuation_mode`：只测旧 PageData、动态绑定的页面分节与 build_document writer。
- `tests/test_render_table_from_html_characterization.py`：701 行，20 个测试。只测旧 table_render_runtime/table_long_renderer writer，HtmlCell/HtmlTable 仅为旧 writer 输入夹具；不包含独立 parser 测试。
  - `test_returns_false_when_html_table_cannot_be_parsed`：只测旧 table_render_runtime/table_long_renderer writer，HtmlCell/HtmlTable 仅为旧 writer 输入夹具；不包含独立 parser 测试。
  - `test_later_th_cells_are_treated_as_table_headers`：只测旧 table_render_runtime/table_long_renderer writer，HtmlCell/HtmlTable 仅为旧 writer 输入夹具；不包含独立 parser 测试。
  - `test_standard_table_marks_rows_for_word_pagination`：只测旧 table_render_runtime/table_long_renderer writer，HtmlCell/HtmlTable 仅为旧 writer 输入夹具；不包含独立 parser 测试。
  - `test_large_simple_table_uses_chunk_renderer`：只测旧 table_render_runtime/table_long_renderer writer，HtmlCell/HtmlTable 仅为旧 writer 输入夹具；不包含独立 parser 测试。
  - `test_split_long_simple_table_rows_uses_word_capacity_without_source_page_scaling`：只测旧 table_render_runtime/table_long_renderer writer，HtmlCell/HtmlTable 仅为旧 writer 输入夹具；不包含独立 parser 测试。
  - `test_render_long_simple_table_uses_single_continuous_table_with_repeating_header`：只测旧 table_render_runtime/table_long_renderer writer，HtmlCell/HtmlTable 仅为旧 writer 输入夹具；不包含独立 parser 测试。
  - `test_numbered_section_table_caption_uses_heading_style`：只测旧 table_render_runtime/table_long_renderer writer，HtmlCell/HtmlTable 仅为旧 writer 输入夹具；不包含独立 parser 测试。
  - `test_remove_table_borders_applies_printable_grid`：只测旧 table_render_runtime/table_long_renderer writer，HtmlCell/HtmlTable 仅为旧 writer 输入夹具；不包含独立 parser 测试。
  - `test_remove_table_borders_uses_configured_border_color`：只测旧 table_render_runtime/table_long_renderer writer，HtmlCell/HtmlTable 仅为旧 writer 输入夹具；不包含独立 parser 测试。
  - `test_fill_table_cell_keeps_header_cell_plain`：只测旧 table_render_runtime/table_long_renderer writer，HtmlCell/HtmlTable 仅为旧 writer 输入夹具；不包含独立 parser 测试。
  - `test_fill_table_cell_applies_configured_header_fill`：只测旧 table_render_runtime/table_long_renderer writer，HtmlCell/HtmlTable 仅为旧 writer 输入夹具；不包含独立 parser 测试。
  - `test_split_long_simple_table_rows_without_source_pages_keeps_default_packing`：只测旧 table_render_runtime/table_long_renderer writer，HtmlCell/HtmlTable 仅为旧 writer 输入夹具；不包含独立 parser 测试。
  - `test_estimate_long_table_page_capacity_subtracts_caption_height`：只测旧 table_render_runtime/table_long_renderer writer，HtmlCell/HtmlTable 仅为旧 writer 输入夹具；不包含独立 parser 测试。
  - `test_large_complex_table_uses_fallback_renderer`：只测旧 table_render_runtime/table_long_renderer writer，HtmlCell/HtmlTable 仅为旧 writer 输入夹具；不包含独立 parser 测试。
  - `test_estimated_table_under_long_threshold_does_not_use_large_table_path`：只测旧 table_render_runtime/table_long_renderer writer，HtmlCell/HtmlTable 仅为旧 writer 输入夹具；不包含独立 parser 测试。
  - `test_small_table_renders_standard_table_and_appends_caption_and_footnote`：只测旧 table_render_runtime/table_long_renderer writer，HtmlCell/HtmlTable 仅为旧 writer 输入夹具；不包含独立 parser 测试。
  - `test_five_column_datasheet_table_uses_wide_description_column`：只测旧 table_render_runtime/table_long_renderer writer，HtmlCell/HtmlTable 仅为旧 writer 输入夹具；不包含独立 parser 测试。
  - `test_terminology_replacement_runs_before_table_parsing`：只测旧 table_render_runtime/table_long_renderer writer，HtmlCell/HtmlTable 仅为旧 writer 输入夹具；不包含独立 parser 测试。
  - `test_render_normalized_text_fragment_handles_sub_sup_without_beautifulsoup`：只测旧 table_render_runtime/table_long_renderer writer，HtmlCell/HtmlTable 仅为旧 writer 输入夹具；不包含独立 parser 测试。
  - `test_render_normalized_text_fragment_falls_back_for_unknown_markup`：只测旧 table_render_runtime/table_long_renderer writer，HtmlCell/HtmlTable 仅为旧 writer 输入夹具；不包含独立 parser 测试。
- `tests/test_translation_runtime_characterization.py`：265 行，10 个测试。只测旧 Block/PageData 翻译提取、批次和响应回填；正式 DocumentIR 翻译不使用它。
  - `test_extract_translation_items_uses_stable_minimal_ids`：只测旧 Block/PageData 翻译提取、批次和响应回填；正式 DocumentIR 翻译不使用它。
  - `test_extract_translation_items_skips_page_decorations`：只测旧 Block/PageData 翻译提取、批次和响应回填；正式 DocumentIR 翻译不使用它。
  - `test_batching_extends_to_complete_section_when_page_boundary_splits_it`：只测旧 Block/PageData 翻译提取、批次和响应回填；正式 DocumentIR 翻译不使用它。
  - `test_batching_splits_oversized_section_by_page_and_marks_continuation`：只测旧 Block/PageData 翻译提取、批次和响应回填；正式 DocumentIR 翻译不使用它。
  - `test_request_payload_keeps_llm_items_minimal`：只测旧 Block/PageData 翻译提取、批次和响应回填；正式 DocumentIR 翻译不使用它。
  - `test_extract_translation_items_includes_cyrillic_text_for_ru2zh`：只测旧 Block/PageData 翻译提取、批次和响应回填；正式 DocumentIR 翻译不使用它。
  - `test_apply_translation_responses_restores_placeholders_and_rewrites_html_cells`：只测旧 Block/PageData 翻译提取、批次和响应回填；正式 DocumentIR 翻译不使用它。
  - `test_build_translation_trace_payload_records_ai_and_final_text`：只测旧 Block/PageData 翻译提取、批次和响应回填；正式 DocumentIR 翻译不使用它。
  - `test_validate_translation_responses_rejects_placeholder_mismatch`：只测旧 Block/PageData 翻译提取、批次和响应回填；正式 DocumentIR 翻译不使用它。
  - `test_load_translation_response_file_accepts_batch_payload`：只测旧 Block/PageData 翻译提取、批次和响应回填；正式 DocumentIR 翻译不使用它。
- `tests/test_page_flow_characterization.py`：74 行，2 个测试。只测旧 Block/RenderConfig 驱动的 page_flow_runtime 分页估算。
  - `test_plan_page_breaks_before_unit_when_anchor_would_be_orphaned`：只测旧 Block/RenderConfig 驱动的 page_flow_runtime 分页估算。
  - `test_table_anchor_includes_caption_and_visible_rows`：只测旧 Block/RenderConfig 驱动的 page_flow_runtime 分页估算。
- `tests/test_runtime_direct_loaders.py`：130 行，4 个测试。只验证待删除 characterization 加载器的替身恢复行为；正式模块直接导入且不使用该加载器。
  - `test_loaders_restore_loaded_modules_and_parent_packages`：只验证待删除 characterization 加载器的替身恢复行为；正式模块直接导入且不使用该加载器。
  - `test_loaders_do_not_leak_missing_modules_or_parent_attributes`：只验证待删除 characterization 加载器的替身恢复行为；正式模块直接导入且不使用该加载器。
  - `test_loaders_restore_partially_loaded_services_package`：只验证待删除 characterization 加载器的替身恢复行为；正式模块直接导入且不使用该加载器。
  - `test_text_loader_does_not_bind_stub_font_rules_to_real_docx`：只验证待删除 characterization 加载器的替身恢复行为；正式模块直接导入且不使用该加载器。
- `tests/runtime_direct_loaders.py`：797 行，0 个测试。仅为旧运行时 characterization 测试构建动态模型/依赖绑定，剩余共享测试改为直接导入。

## 混合测试保留与删除

- `tests/test_render_config_characterization.py`：保留 4 个共享规则用例并改为直接导入；删除 11 个旧运行时用例和专属加载夹具。
  - `test_load_section_layout_uses_template_base_and_yaml_overrides_selected_fields`：调用旧运行时方法或依赖旧模型/动态绑定，不是独立共享规则断言。
  - `test_load_section_layout_falls_back_to_default_layout_without_template_or_config`：调用旧运行时方法或依赖旧模型/动态绑定，不是独立共享规则断言。
  - `test_load_paragraph_styles_maps_yaml_keys_to_word_styles`：调用旧运行时方法或依赖旧模型/动态绑定，不是独立共享规则断言。
  - `test_load_table_style_maps_header_bold_flag`：调用旧运行时方法或依赖旧模型/动态绑定，不是独立共享规则断言。
  - `test_load_render_config_omits_empty_terminology`：调用旧运行时方法或依赖旧模型/动态绑定，不是独立共享规则断言。
  - `test_load_render_config_keeps_non_empty_terminology`：调用旧运行时方法或依赖旧模型/动态绑定，不是独立共享规则断言。
  - `test_resolve_document_language_detects_english_from_page_content`：调用旧运行时方法或依赖旧模型/动态绑定，不是独立共享规则断言。
  - `test_resolve_document_language_honors_explicit_override`：调用旧运行时方法或依赖旧模型/动态绑定，不是独立共享规则断言。
  - `test_apply_document_language_overrides_uses_english_font_without_changing_config_sizes`：调用旧运行时方法或依赖旧模型/动态绑定，不是独立共享规则断言。
  - `test_apply_document_language_overrides_keeps_non_english_config_unchanged`：调用旧运行时方法或依赖旧模型/动态绑定，不是独立共享规则断言。
  - `test_apply_document_language_overrides_preserves_explicit_new_font_fields`：调用旧运行时方法或依赖旧模型/动态绑定，不是独立共享规则断言。
- `tests/test_input_adapter_characterization.py`：保留 4 个共享规则用例并改为直接导入；删除 25 个旧运行时用例和专属加载夹具。
  - `test_parse_v2_block_removes_details_from_content_list_paragraph_text`：调用旧运行时方法或依赖旧模型/动态绑定，不是独立共享规则断言。
  - `test_materialize_input_yields_directory_as_is`：调用旧运行时方法或依赖旧模型/动态绑定，不是独立共享规则断言。
  - `test_materialize_input_extracts_zip_to_temp_directory`：调用旧运行时方法或依赖旧模型/动态绑定，不是独立共享规则断言。
  - `test_materialize_input_rejects_unsupported_path`：调用旧运行时方法或依赖旧模型/动态绑定，不是独立共享规则断言。
  - `test_materialize_input_rejects_zip_path_traversal`：调用旧运行时方法或依赖旧模型/动态绑定，不是独立共享规则断言。
  - `test_load_content_pages_prefers_v2_when_both_exist`：调用旧运行时方法或依赖旧模型/动态绑定，不是独立共享规则断言。
  - `test_load_content_pages_falls_back_to_legacy`：调用旧运行时方法或依赖旧模型/动态绑定，不是独立共享规则断言。
  - `test_load_content_pages_reuses_shared_final_promotional_page_rule`：调用旧运行时方法或依赖旧模型/动态绑定，不是独立共享规则断言。
  - `test_load_content_pages_reuses_final_promotional_page_rule_for_legacy`：调用旧运行时方法或依赖旧模型/动态绑定，不是独立共享规则断言。
  - `test_load_content_pages_error_points_to_nearby_mineru_output_directory`：调用旧运行时方法或依赖旧模型/动态绑定，不是独立共享规则断言。
  - `test_resolve_local_run_options_falls_back_to_configured_input_for_project_root`：调用旧运行时方法或依赖旧模型/动态绑定，不是独立共享规则断言。
  - `test_load_middle_pages_returns_empty_without_middle_json`：调用旧运行时方法或依赖旧模型/动态绑定，不是独立共享规则断言。
  - `test_load_middle_pages_reads_layout_json_page_sizes`：调用旧运行时方法或依赖旧模型/动态绑定，不是独立共享规则断言。
  - `test_parse_v2_block_maps_title_paragraph_and_list`：调用旧运行时方法或依赖旧模型/动态绑定，不是独立共享规则断言。
  - `test_parse_v2_block_preserves_inline_equation_sources_inside_paragraph`：调用旧运行时方法或依赖旧模型/动态绑定，不是独立共享规则断言。
  - `test_parse_v2_block_preserves_html_scripts_and_semantic_formula_sources`：调用旧运行时方法或依赖旧模型/动态绑定，不是独立共享规则断言。
  - `test_parse_v2_block_splits_toc_like_multiline_paragraph`：调用旧运行时方法或依赖旧模型/动态绑定，不是独立共享规则断言。
  - `test_parse_v2_block_keeps_spacing_around_inline_equation_fragments`：调用旧运行时方法或依赖旧模型/动态绑定，不是独立共享规则断言。
  - `test_parse_v2_block_maps_page_decorations_and_equation`：调用旧运行时方法或依赖旧模型/动态绑定，不是独立共享规则断言。
  - `test_parse_legacy_block_maps_text_and_list`：调用旧运行时方法或依赖旧模型/动态绑定，不是独立共享规则断言。
  - `test_resolve_asset_path_returns_real_image_file_from_images_directory`：调用旧运行时方法或依赖旧模型/动态绑定，不是独立共享规则断言。
  - `test_parse_visual_block_maps_visual_metadata`：调用旧运行时方法或依赖旧模型/动态绑定，不是独立共享规则断言。
  - `test_parse_visual_block_merges_numbered_footnote_fragments`：调用旧运行时方法或依赖旧模型/动态绑定，不是独立共享规则断言。
  - `test_parse_visual_block_returns_table_placeholder_for_images_directory`：调用旧运行时方法或依赖旧模型/动态绑定，不是独立共享规则断言。
  - `test_collect_middle_visual_blocks_collects_and_deduplicates_visuals`：调用旧运行时方法或依赖旧模型/动态绑定，不是独立共享规则断言。
- `tests/test_text_render_characterization.py`：保留 13 个共享规则用例并改为直接导入；删除 14 个旧运行时用例和专属加载夹具。
  - `test_prepare_text_applies_terminology_after_formula_normalization`：调用旧运行时方法或依赖旧模型/动态绑定，不是独立共享规则断言。
  - `test_fill_toc_entry_paragraph_uses_dot_leader_tab_for_page_number`：调用旧运行时方法或依赖旧模型/动态绑定，不是独立共享规则断言。
  - `test_fill_toc_entry_paragraph_uses_supplied_usable_width_for_tab_stop`：调用旧运行时方法或依赖旧模型/动态绑定，不是独立共享规则断言。
  - `test_apply_named_style_config_updates_paragraph_format`：调用旧运行时方法或依赖旧模型/动态绑定，不是独立共享规则断言。
  - `test_render_inline_html_into_paragraph_fallback_applies_requested_flags`：调用旧运行时方法或依赖旧模型/动态绑定，不是独立共享规则断言。
  - `test_apply_run_defaults_writes_independent_font_slots`：调用旧运行时方法或依赖旧模型/动态绑定，不是独立共享规则断言。
  - `test_apply_run_defaults_keeps_legacy_single_font_behavior`：调用旧运行时方法或依赖旧模型/动态绑定，不是独立共享规则断言。
  - `test_apply_run_defaults_preserves_explicit_empty_font_inheritance`：调用旧运行时方法或依赖旧模型/动态绑定，不是独立共享规则断言。
  - `test_fill_title_paragraph_uses_cover_title_style_on_first_page`：调用旧运行时方法或依赖旧模型/动态绑定，不是独立共享规则断言。
  - `test_fill_title_paragraph_uses_heading_style_for_numbered_title`：调用旧运行时方法或依赖旧模型/动态绑定，不是独立共享规则断言。
  - `test_fill_title_paragraph_allows_disabling_keep_with_next`：调用旧运行时方法或依赖旧模型/动态绑定，不是独立共享规则断言。
  - `test_fill_body_paragraph_applies_normal_style_and_prepared_text`：调用旧运行时方法或依赖旧模型/动态绑定，不是独立共享规则断言。
  - `test_fill_list_paragraph_uses_word_numbering_without_manual_marker`：调用旧运行时方法或依赖旧模型/动态绑定，不是独立共享规则断言。
  - `test_is_cover_title_rejects_english_contents_heading`：调用旧运行时方法或依赖旧模型/动态绑定，不是独立共享规则断言。
- `tests/test_conversion_sandbox_dev_tools.py`：仅删除 `OfficialConversionRuntimeBindingTests.test_runtime_facade_load_pages_binds_model_classes` 与 facade 导入；该方法只验证旧 facade 的模型绑定。正式 CLI、adapter、沙盒治理、翻译完整性测试全部保留。

## 检查

已完成：三个混合共享规则测试模块合计 21 个用例通过（0.004 秒）。临时目录限定任务目录并已清理；正式 adapter 与其他合并后检查由主会话统一执行。

## 文档与风险

混合测试新模块文档为中文；保留共享源码无改动。未新增兜底、兼容入口或外部调用。未执行完整回归。

## 追加旧 artifact 测试清理

- `tests/test_job_artifact_contract.py`：删除 138 行。仅验证已删除 JobArtifactService/LocalArtifactStorageAdapter 的旧 JobFile alias、路径与下载合同，未直接断言保留模型本身。
  - `test_artifact_alias_file_type_media_type_and_paths_are_stable`：仅验证已删除 JobArtifactService/LocalArtifactStorageAdapter 的旧 JobFile alias、路径与下载合同，未直接断言保留模型本身。
  - `test_parsed_result_package_contract_is_stable`：仅验证已删除 JobArtifactService/LocalArtifactStorageAdapter 的旧 JobFile alias、路径与下载合同，未直接断言保留模型本身。
  - `test_legacy_job_file_without_fingerprint_remains_valid`：仅验证已删除 JobArtifactService/LocalArtifactStorageAdapter 的旧 JobFile alias、路径与下载合同，未直接断言保留模型本身。
  - `test_download_artifact_contract_supports_stream_and_redirect_shapes`：仅验证已删除 JobArtifactService/LocalArtifactStorageAdapter 的旧 JobFile alias、路径与下载合同，未直接断言保留模型本身。
- `tests/test_s3_artifact_storage.py`：删除 108 行。仅验证已删除 S3ArtifactStorageAdapter 的上传与下载，正式 files 的 S3 适配器另有 test_s3_file_upload.py。
  - `test_s3_adapter_uploads_local_artifact_and_returns_presigned_redirect`：仅验证已删除 S3ArtifactStorageAdapter 的上传与下载，正式 files 的 S3 适配器另有 test_s3_file_upload.py。
  - `test_s3_adapter_streams_object_body_when_configured`：仅验证已删除 S3ArtifactStorageAdapter 的上传与下载，正式 files 的 S3 适配器另有 test_s3_file_upload.py。
- `tests/test_artifact_retention.py`：只删 `ArtifactRetentionTests.test_retention_dry_run_selects_local_and_object_artifacts_by_status_and_age`、`_seed_job` 和旧导入；它依赖已删除 jobs 仓储与 ArtifactRetentionPlanner。正式 `DocumentFileRetentionTests.test_document_file_retention_plan_marks_expired_without_deleting_objects` 完整保留。
