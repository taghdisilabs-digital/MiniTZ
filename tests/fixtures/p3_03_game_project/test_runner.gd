extends SceneTree

const FIXTURE_ID := "minitz-p3-03-godot43-real-v1"


func _init() -> void:
	var failures: Array[String] = []
	var packed: PackedScene = load("res://main.tscn") as PackedScene
	if packed == null:
		failures.append("main scene did not load as PackedScene")
	else:
		var instance: Node = packed.instantiate()
		if instance.name != "Main":
			failures.append("root name changed")
		var title := instance.get_node_or_null("Title") as Label
		if title == null or title.text != "MINITZ REAL GODOT 4.3":
			failures.append("title state changed")
		var marker := instance.get_node_or_null("Marker") as Polygon2D
		if marker == null or marker.position != Vector2(160, 92):
			failures.append("marker state changed")
		instance.free()
	var evidence_dir := ProjectSettings.globalize_path("res://evidence/native-test")
	DirAccess.make_dir_recursive_absolute(evidence_dir)
	var untrusted_text := OS.get_environment("MINITZ_UNTRUSTED_TEXT")
	var output := FileAccess.open(evidence_dir.path_join("test_result.json"), FileAccess.WRITE)
	if output == null:
		failures.append("test evidence could not be written")
	else:
		output.store_string(JSON.stringify({
			"fixture_id": FIXTURE_ID,
			"failures": failures,
			"status": "PASS" if failures.is_empty() else "FAIL",
			"untrusted_text": untrusted_text,
		}, "  ", true) + "\n")
		output.close()
	if failures.is_empty():
		print("MINITZ_TEST_PASS fixture=%s" % FIXTURE_ID)
		quit(0)
	else:
		push_error("MINITZ_TEST_FAIL %s" % failures)
		quit(5)
