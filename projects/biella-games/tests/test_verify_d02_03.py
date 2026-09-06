from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))
from verify_d02_03 import verify_npc_contact


def test_npc_contact_accepts_transition_frame_counter_with_both_team_damage():
    phases = {21: [{"impacts": 2.0}], 18: [{"impacts": 3.0}]}
    log = "\n".join([
        "D01_SIGNAL DAMAGE target=BiellaInfected_2 amount=1.0 health=0.0 tag=vehicle_impact source=BiellaStreamingCharacter_0 source_team=0 target_team=2",
        "D01_SIGNAL DAMAGE target=BiellaRival_1 amount=1.0 health=0.0 tag=vehicle_impact source=BiellaStreamingCharacter_0 source_team=0 target_team=1",
        "D02_VEHICLE_TEST event=npc_contact_confirmed phase=21 time=35.0",
    ])
    verify_npc_contact(phases, log)


def test_npc_contact_rejects_missing_team_damage():
    phases = {21: [{"impacts": 2.0}], 18: [{"impacts": 3.0}]}
    log = "D02_VEHICLE_TEST event=npc_contact_confirmed phase=21 time=35.0"
    try:
        verify_npc_contact(phases, log)
    except (AssertionError, ValueError):
        return
    raise AssertionError("missing NPC damage evidence was accepted")
