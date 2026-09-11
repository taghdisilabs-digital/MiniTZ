import hashlib,json,pathlib,unittest
ROOT=pathlib.Path(__file__).resolve().parents[1]
class MiniTZExperienceTests(unittest.TestCase):
 def test_experience_structure(self):
  html=(ROOT/'src/live/index.html').read_text()
  for token in ('id="experience"','id="capabilities"','id="locker"','id="founder"','id="final-film"','data-locker','photo-hero','I couldn’t code.'):
   self.assertIn(token,html)
 def test_live_system_dashboard_is_literal_text_first(self):
  html=(ROOT/'src/live/index.html').read_text()
  for token in ('id="system"','CURRENT TASK','STATUS','PROGRESS','NOW EXECUTING','CODEX','ANTIGRAVITY','COMMANDERS','LOCAL AI','GPU','VALIDATION','SOURCE','HEARTBEAT'):
   self.assertIn(token,html)
  for forbidden in ('<canvas','visual-grid','scanline','background-stack'):
   self.assertNotIn(forbidden,html)
 def test_locker_schema(self):
  p=ROOT/'content/locker-index.json'; self.assertTrue(p.is_file(),p)
  data=json.loads(p.read_text()); self.assertEqual(data['schema'],'minitz.public-locker/v1')
  allowed={'id','timestamp','title','summary','type','capability_tags','media','evidence_summary','evidence_refs','source_revision','status'}
  self.assertTrue(data['entries'])
  for entry in data['entries']: self.assertEqual(set(entry),allowed)
 def test_founder_photo_is_preserved_byte_for_byte(self):
  p=ROOT/'src/live/assets/mahdi-original.jpg'
  self.assertEqual(hashlib.sha256(p.read_bytes()).hexdigest(),'cc743dece94ef855d3f08064b19c0488cb86f4f1dabc5cc922217930fe6458bb')
 def test_film_master_is_real_mp4_media(self):
  p=ROOT/'src/live/assets/minitz-ican-film.mp4'
  self.assertGreater(p.stat().st_size,4_000_000)
  self.assertIn(b'ftyp',p.read_bytes()[:64])
 def test_film_is_final_and_founder_photo_is_not_inside_film_section(self):
  html=(ROOT/'src/live/index.html').read_text()
  self.assertIn('id="final-film"',html)
  self.assertLess(html.index('id="founder"'),html.index('id="final-film"'))
  self.assertEqual(html.count('mahdi-original.jpg'),1)
  film=html[html.index('id="final-film"'):html.index('</section>',html.index('id="final-film"'))]
  self.assertNotIn('mahdi-original.jpg',film)
  self.assertNotIn('autoplay',film)
  self.assertNotIn('muted',film)
  self.assertIn('Play the film',film)

 def test_opening_is_not_a_video_player(self):
  html=(ROOT/'src/live/index.html').read_text()
  opening=html[html.index('id="experience"'):html.index('id="system"')]
  self.assertNotIn('<video',opening)
 def test_final_film_requires_explicit_sound_play(self):
  app=(ROOT/'src/live/app.js').read_text()
  self.assertIn("q('[data-final-film]')",app)
  self.assertIn("q('[data-film-play]')",app)
  self.assertIn('film.muted=false',app)
  self.assertIn('await film.play()',app)

