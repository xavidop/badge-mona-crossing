"""
Mona Crossing: hop across endless roads and rivers without getting flattened.

Dodge the traffic, ride the logs, weave between the trees, and keep moving:
dawdle and the screen leaves you behind. Every row forward is a point and
the badge keeps your best run.

Controls:
* Up / Down / Left / Right = Hop one tile
* Select = Start, or hop again after a splat
* Back = Back to the title
"""

import os
import random
import sys

from badgeware import State

APP_DIR = "/system/apps/mona_crossing"
os.chdir(APP_DIR)
sys.path.insert(0, APP_DIR)

badge.mode(HIRES | VSYNC)
screen.antialias = image.OFF

WIDTH, HEIGHT = screen.width, screen.height

CROSSER = image.load("assets/crosser.png").spritesheet(2, 1)
CAR = image.load("assets/car.png")
TRUCK = image.load("assets/truck.png")
LOG = image.load("assets/log.png")

TILE = 20
COLS = WIDTH // TILE
LOOP = WIDTH + 140          # traffic travels round a loop a little wider than the screen
HOP_MS = 110
IDLE_LIMIT_MS = 6000
CAMERA_ROW = 3              # Mona's row counted from the bottom when the camera is settled
CREEP_ROWS_PER_S = 0.35     # how fast the camera creeps forward on its own
GRASS_ROW, ROAD_ROW, RIVER_ROW = 0, 1, 2

GRASS = (color.rgb(96, 190, 96), color.rgb(84, 176, 84))
ROAD = color.rgb(72, 72, 84)
ROAD_LINE = color.rgb(220, 210, 160)
RIVER = color.rgb(60, 130, 220)
RIVER_LIGHT = color.rgb(110, 170, 240)
TRUNK = color.rgb(120, 80, 40)
CANOPY = color.rgb(40, 130, 60)
INK = color.rgb(20, 20, 32)
CREAM = color.rgb(240, 232, 208)
AMBER = color.rgb(255, 200, 48)
RED = color.rgb(230, 70, 70)
PANEL = color.rgb(20, 20, 32, 190)
SHADOW = color.rgb(0, 0, 0, 80)

TITLE = font.futile
BIG = font.ignore
BODY = font.nope
SMALL = font.sins

TITLE_SCREEN, PLAY, OVER = 0, 1, 2

state = {"best": 0, "games": 0}
State.load("mona_crossing", state)
for key in state:
    if not isinstance(state[key], int) or state[key] < 0:
        state[key] = 0


def save_state():
    try:
        State.save("mona_crossing", state)
    except OSError as error:
        print("Mona Crossing: could not save:", error)


# ----------------------------------------------------------------------------
# the world: rows generated forward on demand

mode = TITLE_SCREEN
rows = []               # index = row number; each a dict with kind and contents
player_row = 0
player_x = 0.0          # pixels, left edge of the 16px sprite
hop = None              # (from_x, from_row, to_x, to_row, started_at)
camera = 0.0            # world row at the bottom edge of the screen
score = 0
last_move = 0
dead_at = 0
death = ""


def make_row(index):
    """Row `index`, in a run of similar rows so roads and rivers feel like crossings."""
    difficulty = min(1.0, index / 120)
    previous = rows[-1] if rows else None
    if index < 4:
        kind, left = GRASS_ROW, 0
    elif previous is not None and previous.get("left", 0) > 0:
        kind, left = previous["kind"], previous["left"] - 1
    else:
        roll = random.random()
        if roll < 0.34:
            kind, left = GRASS_ROW, random.randint(0, 1)
        elif roll < 0.75:
            kind, left = ROAD_ROW, random.randint(0, 2)
        else:
            kind, left = RIVER_ROW, random.randint(0, 1)
    row = {"kind": kind, "left": left, "items": [], "trees": set(), "dir": 1, "speed": 0.0, "length": 24, "truck": False}
    if kind == GRASS_ROW:
        if index >= 4:
            count = random.randint(0, 3 + int(difficulty * 3))
            for n in range(count):
                row["trees"].add(random.randint(0, COLS - 1))
            while len(row["trees"]) > COLS - 6:
                row["trees"].pop()
    else:
        row["dir"] = -1 if (previous is not None and previous["kind"] == kind and previous["dir"] == 1) else 1
        row["speed"] = random.randint(50, 90) + difficulty * random.randint(40, 90)
        if kind == ROAD_ROW:
            row["truck"] = random.random() < 0.3
            row["length"] = 36 if row["truck"] else 24
            spacing = random.randint(110, 170) - int(difficulty * 30)
        else:
            row["length"] = 36
            spacing = random.randint(70, 110)
        count = max(1, LOOP // spacing)
        offset = random.randint(0, spacing)
        row["items"] = [float((offset + n * spacing) % LOOP) for n in range(count)]
    rows.append(row)


def extend_rows():
    while len(rows) < int(camera) + HEIGHT // TILE + 3:
        make_row(len(rows))


def start_game():
    global mode, player_row, player_x, hop, camera, score, last_move, death
    random.seed(badge.ticks)
    del rows[:]
    player_row = 1
    player_x = float((COLS // 2) * TILE + 2)
    hop = None
    camera = 0.0
    score = 0
    death = ""
    extend_rows()
    last_move = badge.ticks
    mode = PLAY


def row_screen_y(row):
    """Screen y of the top of a world row."""
    return HEIGHT - int((row - camera + 1) * TILE)


def item_x(row, base):
    """Where an item on the loop sits on screen for this row's direction."""
    if row["dir"] > 0:
        return base - 70
    return WIDTH + 70 - base - row["length"]


def blocked(col, row_index):
    if col < 0 or col >= COLS or row_index < 0:
        return True
    extend_rows()
    return col in rows[row_index]["trees"]


def try_hop(dcol, drow):
    global hop, last_move
    if hop is not None:
        return
    col = int((player_x - 2 + TILE // 2) // TILE)
    target_col = col + dcol
    target_row = player_row + drow
    if blocked(target_col, target_row):
        return
    hop = (player_x, player_row, float(target_col * TILE + 2), target_row, badge.ticks)
    last_move = badge.ticks


def die(reason):
    global mode, dead_at, death
    death = reason
    dead_at = badge.ticks
    state["games"] += 1
    if score > state["best"]:
        state["best"] = score
    save_state()
    mode = OVER


def update_play(dt):
    global hop, player_row, player_x, camera, score
    now = badge.ticks
    if badge.pressed(BUTTON_UP):
        try_hop(0, 1)
    elif badge.pressed(BUTTON_DOWN):
        try_hop(0, -1)
    elif badge.pressed(BUTTON_LEFT):
        try_hop(-1, 0)
    elif badge.pressed(BUTTON_RIGHT):
        try_hop(1, 0)
    # traffic and logs
    extend_rows()
    low = max(0, int(camera) - 1)
    high = min(len(rows), int(camera) + HEIGHT // TILE + 3)
    for index in range(low, high):
        row = rows[index]
        if row["kind"] != GRASS_ROW:
            step = row["speed"] * dt
            row["items"] = [(x + step) % LOOP for x in row["items"]]
    if hop is not None:
        from_x, from_row, to_x, to_row, started = hop
        t = min(1.0, (now - started) / HOP_MS)
        player_x = from_x + (to_x - from_x) * t
        if t >= 1.0:
            player_row = to_row
            hop = None
            score = max(score, player_row - 1)
    current = rows[player_row]
    if hop is None:
        if current["kind"] == ROAD_ROW:
            for base in current["items"]:
                x = item_x(current, base)
                if x < player_x + 13 and x + current["length"] > player_x + 3:
                    die("SPLAT!")
                    return
        elif current["kind"] == RIVER_ROW:
            riding = None
            for base in current["items"]:
                x = item_x(current, base)
                if x - 4 <= player_x + 8 <= x + current["length"] + 4:
                    riding = x
            if riding is None:
                die("SPLASH!")
                return
            player_x += current["dir"] * current["speed"] * dt
            if player_x < -8 or player_x > WIDTH - 8:
                die("SWEPT AWAY!")
                return
    # the camera follows, and creeps forward on its own once the run has begun
    target = max(camera, player_row - CAMERA_ROW)
    camera += (target - camera) * min(1.0, dt * 6)
    if score > 0:
        camera += CREEP_ROWS_PER_S * dt * (1 + score / 150)
    if player_row < camera - 0.4:
        die("LEFT BEHIND!")
        return
    if now - last_move > IDLE_LIMIT_MS:
        die("CAUGHT NAPPING!")


# ----------------------------------------------------------------------------
# drawing

def fill(x, y, w, h, pen):
    screen.pen = pen
    screen.rectangle(x, y, w, h)


def write(text, x, y, pen, face=BODY):
    screen.font = face
    screen.pen = pen
    screen.text(text, x, y)


def text_width(text, face=BODY):
    screen.font = face
    return screen.measure_text(text)[0]


def write_centred(text, cx, y, pen, face=BODY):
    write(text, cx - text_width(text, face) // 2, y, pen, face)


def write_shadowed(text, cx, y, pen, face=BODY):
    write_centred(text, cx + 2, y + 2, INK, face)
    write_centred(text, cx, y, pen, face)


def draw_item(picture, width, x, y, flip):
    if flip:
        screen.blit(picture, rect(0, 0, width, 12), rect(int(x) + width, y, -width, 12), image.NEAREST)
    else:
        screen.blit(picture, rect(0, 0, width, 12), rect(int(x), y, width, 12), image.NEAREST)


def draw_world():
    low = max(0, int(camera) - 1)
    high = min(len(rows), int(camera) + HEIGHT // TILE + 3)
    for index in range(low, high):
        row = rows[index]
        y = row_screen_y(index)
        if row["kind"] == GRASS_ROW:
            fill(0, y, WIDTH, TILE, GRASS[index % 2])
            for col in row["trees"]:
                fill(col * TILE + 8, y + 10, 4, 8, TRUNK)
                screen.pen = CANOPY
                screen.shape(shape.circle(col * TILE + 10, y + 7, 7))
        elif row["kind"] == ROAD_ROW:
            fill(0, y, WIDTH, TILE, ROAD)
            if index > 0 and rows[index - 1]["kind"] == ROAD_ROW:
                for x in range(4, WIDTH, 24):
                    fill(x, y, 12, 2, ROAD_LINE)
        else:
            fill(0, y, WIDTH, TILE, RIVER)
            ripple = int(badge.ticks // 200 + index * 7) % 40
            for x in range(ripple, WIDTH, 40):
                fill(x, y + 6 + (index % 3) * 4, 10, 2, RIVER_LIGHT)
    for index in range(low, high):
        row = rows[index]
        if row["kind"] == GRASS_ROW:
            continue
        y = row_screen_y(index) + 4
        picture = LOG if row["kind"] == RIVER_ROW else (TRUCK if row["truck"] else CAR)
        for base in row["items"]:
            x = item_x(row, base)
            if -40 < x < WIDTH:
                draw_item(picture, row["length"], x, y, row["dir"] < 0 and row["kind"] == ROAD_ROW)


def draw_player():
    row = player_row
    lift = 0
    frame = 0
    if hop is not None:
        t = min(1.0, (badge.ticks - hop[4]) / HOP_MS)
        row = hop[1] + (hop[3] - hop[1]) * t
        lift = int(6 * (1 - (2 * t - 1) ** 2))
        frame = 1
    y = HEIGHT - int((row - camera + 1) * TILE) + 2
    fill(int(player_x) + 2, y + 12, 12, 4, SHADOW)
    screen.blit(CROSSER.sprite(frame, 0), rect(0, 0, 16, 16), rect(int(player_x), y - lift, 16, 16), image.NEAREST)


def draw_hud():
    fill(0, 0, WIDTH, 16, PANEL)
    write("%d" % score, 6, 2, AMBER, BODY)
    write("BEST %d" % state["best"], WIDTH - 6 - text_width("BEST %d" % state["best"], BODY), 2, CREAM, BODY)


def draw_title():
    draw_world()
    draw_player()
    fill(20, 26, WIDTH - 40, 92, PANEL)
    write_shadowed("MONA CROSSING", WIDTH // 2, 34, AMBER, BIG)
    write_shadowed("HOP ACROSS - DON'T DAWDLE", WIDTH // 2, 66, CREAM, SMALL)
    if (badge.ticks // 400) % 2:
        write_shadowed("SELECT TO HOP", WIDTH // 2, 88, CREAM, BODY)
    if state["games"]:
        write_shadowed("BEST %d ROWS IN %d RUNS" % (state["best"], state["games"]), WIDTH // 2, 222, AMBER, SMALL)


def draw_over():
    draw_world()
    if badge.ticks - dead_at < 500:
        # a squashed Mona for a moment
        y = HEIGHT - int((player_row - camera + 1) * TILE) + 10
        screen.blit(CROSSER.sprite(0, 0), rect(0, 0, 16, 16), rect(int(player_x) - 4, y, 24, 8), image.NEAREST)
    else:
        draw_player()
    draw_hud()
    fill(30, 50, WIDTH - 60, 120, PANEL)
    write_shadowed(death, WIDTH // 2, 60, RED, BIG)
    write_centred("%d ROWS" % score, WIDTH // 2, 94, AMBER, TITLE)
    write_centred("NEW BEST!" if score >= state["best"] and score > 0 else "BEST %d" % state["best"], WIDTH // 2, 122, CREAM, BODY)
    if badge.ticks - dead_at > 600 and (badge.ticks // 400) % 2:
        write_centred("SELECT: AGAIN   BACK: TITLE", WIDTH // 2, 148, CREAM, SMALL)


def update():
    global mode
    dt = min(badge.ticks_delta, 50) / 1000
    if mode == TITLE_SCREEN:
        if not rows:
            random.seed(badge.ticks)
            extend_rows()
        for row in rows:
            if row["kind"] != GRASS_ROW:
                row["items"] = [(x + row["speed"] * dt) % LOOP for x in row["items"]]
        if badge.pressed(BUTTON_SELECT):
            start_game()
        draw_title()
    elif mode == PLAY:
        if badge.pressed(BUTTON_BACK):
            mode = TITLE_SCREEN
            return
        update_play(dt)
        if mode != PLAY:
            return
        draw_world()
        draw_player()
        draw_hud()
    else:
        if badge.ticks - dead_at > 600:
            if badge.pressed(BUTTON_SELECT):
                start_game()
            elif badge.pressed(BUTTON_BACK):
                mode = TITLE_SCREEN
        draw_over()


def on_exit():
    save_state()


player_x = float((COLS // 2) * TILE + 2)
player_row = 1
run(update)
