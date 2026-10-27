import sys; sys.path.insert(0, '/state'); import kit, time
g, update = kit.load('/state/dev_crossing', 'mona_crossing')
_, avg, raw = kit.run_for(update, 400); kit.shot('title', raw, avg)
kit.step(update, (BUTTON_SELECT,)); kit.step(update)
def hop(button, wait=160):
    kit.step(update, (button,))
    return kit.run_for(update, wait)
def safe_ahead():
    # is the tile ahead free of traffic for the hop? crude: no car within 40px of Mona's column
    rows = g['rows']; r = rows[g['player_row'] + 1]
    if r['kind'] == g['GRASS_ROW']:
        col = int((g['player_x'] - 2 + 10) // 20)
        return col not in r['trees']
    for base in r['items']:
        x = g['item_x'](r, base)
        if r['kind'] == g['ROAD_ROW'] and x - 30 < g['player_x'] < x + r['length'] + 30: return False
        if r['kind'] == g['RIVER_ROW'] and x <= g['player_x'] + 8 <= x + r['length']: return True
    return r['kind'] == g['ROAD_ROW']
hops = 0; worst = 0; start = time.ticks_ms()
while g['mode'] == g['PLAY'] and time.ticks_diff(time.ticks_ms(), start) < 25000:
    if g['hop'] is None and safe_ahead():
        w, avg, raw = hop(BUTTON_UP); hops += 1
    else:
        rows = g['rows']; r = rows[g['player_row'] + 1]
        if g['hop'] is None and r['kind'] == g['GRASS_ROW']:
            w, avg, raw = hop(BUTTON_LEFT if g['player_x'] > 160 else BUTTON_RIGHT); hops += 1
        else:
            w, avg, raw = kit.run_for(update, 60)
    worst = max(worst, w)
    if hops == 6: kit.shot('early rows', raw, avg)
    if hops == 14: kit.shot('mid run', raw, avg)
print('  hops', hops, 'score', g['score'], 'mode', g['mode'], 'death', repr(g['death']), 'worst frame', worst, 'rows made', len(g['rows']), 'kinds', [r['kind'] for r in g['rows'][:16]])
if g['mode'] == g['PLAY']:
    # walk into traffic on purpose to see the splat
    ok, raw, cost = kit.run_until(update, lambda: g['mode'] != g['PLAY'], 9000, ())
_, avg, raw = kit.run_for(update, 300); kit.shot('death moment', raw, avg)
_, avg, raw = kit.run_for(update, 700); kit.shot('game over', raw, avg)
g['on_exit'](); print('DONE crossing state', g['state'], 'death', g['death'])
