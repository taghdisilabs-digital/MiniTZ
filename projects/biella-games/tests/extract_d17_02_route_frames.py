#!/usr/bin/env python3
"""Extract unmodified video frames at measured native route events for inspection."""
import argparse
import json
from pathlib import Path
import subprocess
from run_d08_01_release import identity, write

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('capture',type=Path)
args=parser.parse_args();root=args.capture.resolve()
measured=json.loads((root/'measurements.json').read_text())
assert measured['video_decode']['returncode']==0 and not measured['video_decode']['diagnostics']
video=identity(root/'raw-gameplay.mkv')
assert video==measured['evidence']['raw-gameplay.mkv']
frames=[]
for beat,name in [('Traverse the real broken panel opening','panel-exit'),
                  ('Turn inside hall with real camera collision','hall-turn'),
                  ('Terrace ramp foot','ramp-foot'),('Ascend ramp','ramp-ascent'),
                  ('Terrace summit','terrace-summit'),('Terrace overlook at normal camera distance','terrace-overlook'),
                  ('Descend ramp','ramp-descent'),('Return to street','street-return')]:
    stage=next((r for r in measured['stages'] if r['beat']==beat),None)
    if stage is None:continue
    target=root/(name+'.png');assert not target.exists(),'Keep previous extracted frame'
    subprocess.run(['ffmpeg','-nostdin','-v','error','-ss',str(stage['video_seconds']),'-i',str(root/'raw-gameplay.mkv'),
                    '-frames:v','1',str(target)],check=True)
    frames.append(dict(**identity(target),video_seconds=stage['video_seconds'],
                       native_frame=stage['native_frame'],route_stage=stage['index'],beat=beat))
write(root/'frames.json',dict(task_id='D17-02',raw_video=video,extractor=identity(__file__),
      extraction='Unmodified ffmpeg video frame at measured route event time; approximate native-frame mapping at 30 fps. No compositing, grading or rendering.',frames=frames))
print(json.dumps(dict(extracted=len(frames),path=str(root/'frames.json'))))
