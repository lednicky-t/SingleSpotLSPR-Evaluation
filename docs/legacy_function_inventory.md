# Yang_LSPR_evaluation Function Inventory

This is the function and class inventory extracted from the legacy `Yang_LSPR_evaluation` project.
It is grouped by file so we can migrate features into the new suite-local single-spot evaluation app one by one.

## `main.py`

- `_clamp_int`
- `compute_ui_scale`
- `apply_ui_font`
- `_find_logo_path`
- `_app_icon`
- `_logo_pixmap`
- `_instantiate_gui`
- `ThemeManager`
- `MainGUI`

## `data_hdf5_gui.py`

- `MainWin`
- `__init__`
- `_host_main`
- `toast`
- `_pp_col_index`
- `eventFilter`
- `_cycle_tab`
- `_on_unit_change`
- `_apply_view_folding`
- `_pp_expand_hidden_cols`
- `_choose_key_columns`
- `_del_rows`
- `_pp_context_menu`
- `_open_import_build`
- `load_raw`
- `save_h5`
- `open_h5`
- `save_and_refresh`
- `on_pump_load_csv_standard`
- `on_pump_export`
- `on_tree_item_clicked`
- `_read_pump_plan_df_from_h5obj`
- `_get_selected_h5_path`
- `_is_protected_path`
- `_on_tree_rename_doubleclick`
- `_new_group_h5`
- `_rename_h5_node`
- `_on_tree_ctx_menu`
- `_delete_h5_node`
- `_busy`
- `_on_hdf5_subtab_changed`

## `sensorgram_gui.py`

- `SensorgramGUI`
- `__init__`
- `_setup_spin`
- `_style_indicator`
- `_set_labels_position`
- `_step_edit_available`
- `_rebuild_plan_segments_from_current_plan`
- `_get_plan_row_float`
- `_set_plan_row_float`
- `_step_handle_candidates`
- `_hit_test_step_handle`
- `_snap_step_boundary_value`
- `_snap_step_outer_value`
- `_apply_step_outer_edit`
- `_apply_step_boundary_edit`
- `_menu_global_pos`
- `_click_hits_any_label`
- `_build_labels_bar`
- `_init_crop_state_defaults`
- `_current_spectrum_params`
- `_sync_spec_params`
- `_reprocess_selected_and_draw`
- `_set_wl_preview`
- `_prompt_threshold_frac`
- `_prompt_manual_range`
- `_set_crop_mode`
- `_sync_crop_menu_checks`
- `_on_preprocess_changed`
- `_update_ylims_from_data`
- `_on_spectrumproc_changed`
- `_on_recompute_sensorgram`
- `set_pick_mode`
- `_on_toolbar_enlspr_toggled`
- `clear_selections`
- `_interp_to_grid`
- `export_all_selected_spectra`
- `open_colorize_dialog`
- `select_h5`
- `populate_h5_tree`
- `_add_h5_children`
- `on_tree_item_clicked`
- `_read_pump_plan_df_from_hdf5`
- `_select_active_trace`
- `_compute_traces_from_hdf5`
- `build_sensorgram_from_hdf5`
- `_default_ylabel_for_feature`
- `_on_trace_changed`
- `run_pipeline`
- `export_stats`
- `export_sensorgram_traces`
- `save_figure`
- `_on_label_mode_toggled`
- `_on_step_edit_toggled`
- `_collect_label_export_tables`
- `_on_canvas_click`
- `_mpl_px_to_global`
- `_ensure_custom_pos_from_artist`
- `_nudge_selected_labels`
- `_on_pick_text`
- `_start_label_drag`
- `_blit_begin_drag`
- `_blit_draw_drag`
- `_blit_end_drag`
- `_on_mouse_press`
- `_on_mouse_move`
- `_on_mouse_release`
- `_on_key_press`
- `_nudge_selected_labels_xy`
- `_set_active_label`
- `_delete_active_label`
- `_set_selected_label_color`
- `_bump_selected_label_font`
- `_clear_label_selection`
- `_snapshot_label_state`
- `_restore_label_state`
- `_push_undo_state`
- `undo_labels`
- `redo_labels`
- `_get_desc_text_for_seg`
- `_edit_substance_label`
- `request_refresh`
- `refresh_if_ready`
- `draw_plot`
- `open_save_dialog`
- `_build_export_figure`
- `_build_report_table_df`
- `log`
- `_toast`
- `_bump_log_font`
- `log_segments`
- `_show_label_popup`
- `_set_labelbar_visible`
- `_on_add_new_toggled`
- `_arm_add_new_label`
- `_find_label_artist`
- `_cancel_deferred_clear`
- `_schedule_deferred_clear`
- `_draw_extra_user_labels`
- `_hit_test_label`
- `_refresh_label_selection_visuals`
- `_ctrl_down_from_event`
- `_force_all_labels_not_animated`
- `_open_label_context_menu_shortcut`

## `converters/file_readers.py`

- `read_csv_head`
- `parse_raw_light_source`
- `load_time_series`
- `load_matrix_any`

## `converters/pump_plan_io.py`

- `_compute_internal_cols`
- `std_to_internal`
- `internal_to_std`

## `converters/pump_plan_parser.py`

- `_clean_cols_and_values`
- `_try_read_csv`
- `_norm_hex`
- `_to_int_seconds`
- `parse_pump_plan_segments`
- `segments_to_indices`

## `converters/pump_plan_BS_trans.py`

- `_clean_cols_and_values`
- `_try_read_csv`
- `_norm_hex`
- `_to_int_seconds`
- `parse_pump_plan_segments`
- `segments_to_indices`

## `converters/pump_plan_LBL_trans.py`

- `_clean_cols_and_values`
- `_try_read_csv`
- `_norm_hex`
- `_to_int_seconds`
- `parse_pump_plan_segments`
- `segments_to_indices`

## `preprocessing/preprocessing.py`

- `SpectraPreprocessor`
- `auto_crop_peak_to_end`

## `preprocessing/feature_extraction.py`

- `SpectraFeatureExtractor`
- `detect_peak`
- `compute_centroid`
- `compute_fwhm`
- `compute_inflection_points_after_peak`
- `extract_all_features`

## `preprocessing/extinction_calculation.py`

- `calculate_extinction`

## `analysis/fitting.py`

- `gaussian_model`
- `lorentzian_model`
- `polynomial_model`
- `perform_gaussian_fitting`
- `perform_lorentzian_fitting`
- `perform_polynomial_fitting`

## `analysis/fitting_models.py`

- `smooth`
- `threshold_crop`
- `compute_mse`
- `poly_fit`
- `gaussian`
- `gaussian_fit`
- `fourier_series`
- `fourier_fit`
- `sinusoidal`
- `sinus_fit`

## `tasks/import_task.py`

- `ImportTask`
