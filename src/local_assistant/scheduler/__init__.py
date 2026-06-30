"""APScheduler jobs (persistent jobstore in SQLite).

Proactive triggers: reminder firing, morning/evening digest, nightly reflection +
memory consolidation. Respects quiet hours and the daily proactive cap. (phase 5-6)
"""
