extends Node2D

const FIXTURE_ID := "biella-p3-03-godot43-real-v1"
const TERMINAL_FRAME := 30

var mode := "run"
var frame_count := 0
var simulated_seconds := 0.0
var started_usec := 0
var evidence_dir := "res://evidence"


func _ready() -> void:
	started_usec = Time.get_ticks_usec()
	for argument in OS.get_cmdline_user_args():
		if argument.begins_with("--mode="):
			mode = argument.trim_prefix("--mode=")
		elif argument.begins_with("--evidence="):
			evidence_dir = argument.trim_prefix("--evidence=")
	print("BIELLA_RUNTIME_READY fixture=%s mode=%s" % [FIXTURE_ID, mode])
	if mode == "crash":
		call_deferred("_deliberate_crash")


func _process(delta: float) -> void:
	frame_count += 1
	simulated_seconds += delta
	$Marker.rotation = float(frame_count) * 0.05
	if frame_count < TERMINAL_FRAME:
		return
	set_process(false)
	var state := {
		"fixture_id": FIXTURE_ID,
		"engine": Engine.get_version_info().get("string", "unknown"),
		"frame_count": frame_count,
		"main_scene": get_tree().current_scene.scene_file_path,
		"marker_position": [int($Marker.position.x), int($Marker.position.y)],
		"state": "ready",
		"title": $Title.text,
	}
	var profile := {
		"fixture_id": FIXTURE_ID,
		"frame_count": frame_count,
		"fps": Performance.get_monitor(Performance.TIME_FPS),
		"process_seconds": Performance.get_monitor(Performance.TIME_PROCESS),
		"physics_process_seconds": Performance.get_monitor(Performance.TIME_PHYSICS_PROCESS),
		"static_memory_bytes": int(Performance.get_monitor(Performance.MEMORY_STATIC)),
		"node_count": int(Performance.get_monitor(Performance.OBJECT_NODE_COUNT)),
		"draw_calls_last_frame": int(Performance.get_monitor(Performance.RENDER_TOTAL_DRAW_CALLS_IN_FRAME)),
		"simulated_seconds": simulated_seconds,
		"wall_elapsed_usec": Time.get_ticks_usec() - started_usec,
	}
	if not _write_json("runtime_state.json", state):
		get_tree().quit(7)
		return
	if not _write_json("profile.json", profile):
		get_tree().quit(8)
		return
	if mode == "capture" and not _write_capture_png("capture.png"):
		get_tree().quit(9)
		return
	print("BIELLA_RUNTIME_STATE %s" % JSON.stringify(state, "", true))
	print("BIELLA_PROFILE %s" % JSON.stringify(profile, "", true))
	get_tree().quit(0)


func _write_json(filename: String, payload: Dictionary) -> bool:
	var absolute_dir := ProjectSettings.globalize_path(evidence_dir)
	var error := DirAccess.make_dir_recursive_absolute(absolute_dir)
	if error != OK:
		push_error("BIELLA_EVIDENCE_DIR_FAILED code=%d" % error)
		return false
	var output_path := absolute_dir.path_join(filename)
	var output := FileAccess.open(output_path, FileAccess.WRITE)
	if output == null:
		push_error("BIELLA_EVIDENCE_WRITE_FAILED path=%s" % output_path)
		return false
	output.store_string(JSON.stringify(payload, "  ", true) + "\n")
	output.close()
	return true


func _write_capture_png(filename: String) -> bool:
	var image := Image.create(320, 180, false, Image.FORMAT_RGBA8)
	image.fill(($Background as ColorRect).color)
	var accent_color: Color = ($Accent as Polygon2D).color
	var marker_color: Color = ($Marker as Polygon2D).color
	for y in range(46, 123):
		var accent_half_width: int = int(float(y - 46) * 46.0 / 76.0)
		for x in range(160 - accent_half_width, 161 + accent_half_width):
			image.set_pixel(x, y, accent_color)
	for y in range(82, 103):
		var marker_half_width: int = 10 - abs(y - 92)
		for x in range(150, 161 + marker_half_width):
			image.set_pixel(x, y, marker_color)
	var absolute_dir := ProjectSettings.globalize_path(evidence_dir)
	var error := DirAccess.make_dir_recursive_absolute(absolute_dir)
	if error != OK:
		push_error("BIELLA_CAPTURE_DIR_FAILED code=%d" % error)
		return false
	error = image.save_png(absolute_dir.path_join(filename))
	if error != OK:
		push_error("BIELLA_CAPTURE_WRITE_FAILED code=%d" % error)
		return false
	print("BIELLA_CAPTURE_WRITTEN fixture=%s width=320 height=180" % FIXTURE_ID)
	return true


func _deliberate_crash() -> void:
	print("BIELLA_CRASH_FIXTURE fixture=%s" % FIXTURE_ID)
	_write_json("crash_marker.json", {
		"fixture_id": FIXTURE_ID,
		"failure": "deliberate-engine-crash",
	})
	OS.crash("BIELLA_P3_03_DELIBERATE_CRASH")
