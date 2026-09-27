"""Numbers that were literals in the middle of a line.

Only the ones whose value is a judgement call live here: a tuning number someone may want to
revisit, or a timeout whose length is a decision rather than a fact. A 2 that means "a pair"
stays a 2 -- naming it would add a hop without adding meaning.
"""

# Player position is sent at most this often. The overlay redraws far faster, but the panel
# and the steps plaque do not need to.
PLAYER_EMIT_HZ = 15

# Stats and preview go out on their own, slower clocks: both are read by a human, not by code.
STATS_INTERVAL_S = 0.25
PREVIEW_INTERVAL_S = 0.25

# The preview is a diagnostic thumbnail, not a picture worth the bandwidth of a full frame.
PREVIEW_MAX_WIDTH = 480
PREVIEW_JPEG_QUALITY = 70

# A frame is compared to the previous one on every Nth pixel before any real work: an
# unchanged screen is the common case while the player reads their quest log.
FRAME_CHANGE_PROBE_STRIDE = 8

# Shutdown waits. Long enough for a frame in flight to finish, short enough that a wedged one
# does not become a wedged application.
ENGINE_SHUTDOWN_WAIT_MS = 2000
TILES_SHUTDOWN_WAIT_MS = 2000
DETECTOR_JOIN_S = 1.0
