import pygame, math, random, os, wave, struct, json, time, urllib.request, threading, sys, copy

pygame.init(); pygame.mixer.init()

if not getattr(pygame, "IS_CE", False):
    print("\n" + "="*60 + "\n❌ ERROR: Standard Pygame detected! You MUST use Pygame-CE.\n" + "="*60 + "\n"); pygame.quit(); sys.exit()

infoObject = pygame.display.Info()
WIDTH, HEIGHT = infoObject.current_w, infoObject.current_h
screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.FULLSCREEN)
pygame.display.set_caption("Peggle Idle/Upgrades (CE Edition)")
clock = pygame.time.Clock(); FPS = 60
SAVE_FILE = "peggle_save_v18.json"; SETTINGS_FILE = "peggle_settings.json"

# --- CLOUD CONFIGURATION ---
GAS_WEB_APP_URL = "https://script.google.com/macros/s/AKfycby49YtvS7XGC4slE2zhLQ9nkNHvXI_soBctLUnxhqMWw0NM9RU-Tk9W3ThkAvJX5ClL/exec"
current_user = ""; current_pass = ""

GREEN = (50, 200, 50); GOLD = (255, 215, 0); WHITE = (255, 255, 255); BLACK = (20, 20, 30); DARK_BG = (25, 30, 40) 
RED = (255, 50, 50); GRAY = (150, 150, 150); DARK_GRAY = (60, 60, 60); BROWN = (139, 69, 19); BRONZE = (205, 127, 50)    
TAN = (210, 180, 140); CYAN = (50, 255, 255); LIGHT_BLUE = (100, 200, 255); ORANGE = (255, 140, 0); PURPLE = (150, 50, 200)
MAROON = (128, 0, 0); DARK_BLUE = (30, 40, 80); MAGENTA = (255, 0, 255); YELLOW = (255, 255, 0)

dim_overlay = pygame.Surface((WIDTH, HEIGHT)); dim_overlay.set_alpha(200); dim_overlay.fill(BLACK)
font_huge = pygame.font.SysFont(None, 80); font_large = pygame.font.SysFont(None, 48)
font_med = pygame.font.SysFont(None, 36); font_small = pygame.font.SysFont(None, 24); font_tiny = pygame.font.SysFont(None, 18)

def create_sound(filename, is_crunch):
    if not os.path.exists(filename):
        sr = 44100; d = 0.15 if is_crunch else 0.05
        wavef = wave.open(filename, 'w'); wavef.setnchannels(1); wavef.setsampwidth(2); wavef.setframerate(sr)
        for i in range(int(sr * d)):
            v = int(32767.0 * (random.random() * 2.0 - 1.0) * 0.8) if is_crunch else int(32767.0 * math.sin(600.0 * math.pi * 2.0 * i / sr))
            e = ((1.0 - (i / (sr * d)))**4) if is_crunch else (1.0 - (i / (sr * d)))
            wavef.writeframesraw(struct.pack('<h', int(v * e)))
        wavef.close()

create_sound("bounce.wav", False); create_sound("bite.wav", True)
bounce_sound = pygame.mixer.Sound("bounce.wav"); bounce_sound.set_volume(0.2) 
bite_sound = pygame.mixer.Sound("bite.wav"); bite_sound.set_volume(0.4)

BALL_TYPES = {
    "Regular": {"color": RED, "base_grav": 0.25, "base_bounce": 0.85, "cost": 0, "desc": "Gains $5 on wall bounce"},
    "Fire":    {"color": ORANGE, "base_grav": 0.25, "base_bounce": 0.70, "cost": 2500, "desc": "Sets pegs on fire!"},
    "Boulder": {"color": DARK_GRAY, "base_grav": 0.45, "base_bounce": 0.50, "cost": 1500, "desc": "Smashes 3 pegs on ground hit"},
    "Bomb":    {"color": DARK_BLUE, "base_grav": 0.30, "base_bounce": 0.60, "cost": 5000, "desc": "Explodes into shrapnel"},
    "Bouncy":  {"color": CYAN, "base_grav": 0.15, "base_bounce": 0.95, "cost": 15000, "desc": "Multiplier grows on wall hits"},
    "Maroon":  {"color": MAROON, "base_grav": 0.35, "base_bounce": 0.70, "cost": 50000, "desc": "Bounces off the bottom once"},
    "Hoops":   {"color": ORANGE, "base_grav": 0.25, "base_bounce": 0.92, "cost": 150000, "desc": "Teleports to top on drop"},
    "Taco":    {"color": YELLOW, "base_grav": 0.30, "base_bounce": 0.60, "cost": 15000000, "desc": "Eats 3 pegs at once. Breaks in 2-4 hits!"},
    "Magic":   {"color": PURPLE, "base_grav": 0.0, "base_bounce": 0.90, "cost": 500000, "desc": "Floats & Zaps"},
    "Wood":    {"color": BROWN, "base_grav": 0.30, "base_bounce": 0.65, "cost": 1000000, "desc": "Passively grows money mid-air"},
    "Shrapnel": {"color": GRAY, "base_grav": 0.30, "base_bounce": 0.60, "cost": 0, "desc": "", "hidden": True} 
}
ABILITIES = {"Fire Cursor": {"desc": "5s Buff: Hold click to burn pegs", "color": ORANGE, "rarity": "Common"}, "Vacuum Cursor": {"desc": "5s Buff: Hold click to juggle balls!", "color": LIGHT_BLUE, "rarity": "Common"}, "Thunder Cloud": {"desc": "Click to blast 5 random pegs!", "color": DARK_GRAY, "rarity": "Rare"}, "Bounce Revive": {"desc": "Instantly gives active balls an extra bounce!", "color": GREEN, "rarity": "Rare"}, "Midas Touch": {"desc": "Click to turn an area of pegs into Gold!", "color": GOLD, "rarity": "Epic"}, "Starfall": {"desc": "Instantly drops 10 bouncy balls!", "color": LIGHT_BLUE, "rarity": "Epic"}, "Drone": {"desc": "Collects 10 balls. Click to drop them!", "color": WHITE, "rarity": "Epic"}, "Revive Wave": {"desc": "Teleports active balls back to the top!", "color": CYAN, "rarity": "Legendary"}, "Black Hole": {"desc": "Sucks pegs for 6s. Pegs eaten pay 2x!", "color": PURPLE, "rarity": "Legendary"}, "Orbital Strike": {"desc": "Blasts a vertical column with a laser!", "color": RED, "rarity": "Legendary"}}
RARITY_COLORS = {'Common': GRAY, 'Rare': LIGHT_BLUE, 'Epic': PURPLE, 'Legendary': GOLD}
CRATES = {"Basic Crate": {"cost": 2000, "rolls": 3, "odds": {"Legendary": 0.02, "Epic": 0.08, "Rare": 0.30, "Common": 0.60}, "color": BROWN}, "Advanced Crate": {"cost": 10000, "rolls": 6, "odds": {"Legendary": 0.08, "Epic": 0.20, "Rare": 0.42, "Common": 0.30}, "color": DARK_GRAY}, "Premium Crate": {"cost": 40000, "rolls": 10, "odds": {"Legendary": 0.25, "Epic": 0.40, "Rare": 0.25, "Common": 0.10}, "color": GOLD}}
PRESTIGE_DEFS = {'starter_cash': {'name': 'Starter Money', 'desc': '+$1000 on Prestige', 'base_cost': 5, 'max_lvl': 10}, 'extra_rainbow': {'name': 'More Rainbows', 'desc': '+1 Rainbow Peg', 'base_cost': 15, 'max_lvl': 5}, 'bomb_chance': {'name': 'Bomb Chance', 'desc': '+2% Bomb spawn rate', 'base_cost': 10, 'max_lvl': 10}, 'extra_prestige': {'name': 'Prestige Pegs', 'desc': '+1 Brown Peg', 'base_cost': 12, 'max_lvl': 5}, 'gold_chance': {'name': 'Gold Rush', 'desc': '+5% Gold Peg rate', 'base_cost': 10, 'max_lvl': 10}, 'multishot': {'name': 'Multishot', 'desc': '+1 Ball per manual shot', 'base_cost': 25, 'max_lvl': 5}, 'stat_pegs': {'name': 'Stat Pegs', 'desc': '+10% Stat Peg rate', 'base_cost': 15, 'max_lvl': 5}}

state = "LOGIN"; view_only_tree = False; cash = 0; prestige_points = 0; stat_points = 0; boards_cleared = 0
equipped_ball = "Regular"; ability_inventory = {k: 0 for k in ABILITIES.keys()}; equipped_abilities = []; active_ability_mode = None 
custom_maps_unlocked = False; approved_maps_list = []; pending_maps_list = []

editor_pegs = []; editor_bumpers = []; editor_tool = 'green'; editor_is_unfair = False; editor_snap = True
is_playtest = False; backup_pegs = []; backup_bumpers = []; backup_cash = 0
is_uploading = False; upload_message = ""

input_username = ""; input_password = ""; active_input = "username"
admin_input_user = ""; admin_input_amount = ""; admin_active_input = "user"; admin_msg = ""
auth_message = ""; is_authenticating = False; gift_popup_msg = ""
last_save_time = time.time(); offline_rewards = {}; anim_cash = 0.0; anim_pp = 0.0; anim_sp = 0.0; crate_results_display = []
p_upgrades = {k: 0 for k in PRESTIGE_DEFS.keys()}
balls = []; pegs = []; bumpers = []; particles = []; lightnings = []; clouds = []; black_holes = []; lasers = []; drones = []
fire_cursor_timer = 0; vacuum_cursor_timer = 0

CANNON_POS = (WIDTH // 2, 40); PEG_RADIUS = 12; BALL_RADIUS = 10; board_clear_timer = 0; event_text_str = ""; event_timer = 0

def get_default_ball_stats(unlocked=False): return {'unlocked': unlocked, 'level': 1, 'gold_mult': 1.0, 'bounce_bonus': 0.0, 'max_balls': 1, 'auto_drop_lvl': 0, 'upg_cost_power': 50, 'upg_cost_balls': 100, 'upg_cost_auto': 250, 'auto_timer': 0, 'auto_enabled': True, 'special_unlocked': False, 'base_top_revives': 0, 'base_bounce_revives': 0}
ball_stats = {name: get_default_ball_stats(unlocked=(name=="Regular")) for name in BALL_TYPES.keys()}

def format_time(s):
    m, s = divmod(s, 60); h, m = divmod(m, 60)
    return f"{h}h {m}m" if h > 0 else f"{m}m {s}s"

def draw_btn(surface, rect, color, text, font, text_color=BLACK, outline=True):
    shadow = rect.copy(); shadow.y += 4
    pygame.draw.rect(surface, (max(0, color[0]-50), max(0, color[1]-50), max(0, color[2]-50)), shadow, border_radius=8)
    pygame.draw.rect(surface, color, rect, border_radius=8)
    if outline: pygame.draw.rect(surface, WHITE if color != WHITE else BLACK, rect, 2, border_radius=8)
    txt_surf = font.render(text, True, text_color)
    surface.blit(txt_surf, (rect.centerx - txt_surf.get_width()//2, rect.centery - txt_surf.get_height()//2))

def get_rainbow_color():
    t = pygame.time.get_ticks() / 300.0; return (int((math.sin(t)+1)*127.5), int((math.sin(t+2)+1)*127.5), int((math.sin(t+4)+1)*127.5))

def draw_peg_visual(surface, x, y, p_type, hp=0, is_fire=False):
    color = ORANGE if is_fire else (get_rainbow_color() if p_type == 'rainbow' else (GOLD if p_type == 'gold' else (DARK_GRAY if p_type == 'bomb' else (BROWN if p_type == 'prestige' else (MAGENTA if p_type == 'boss' else (CYAN if p_type == 'stat' else (GRAY if p_type == 'random' else GREEN)))))))
    rad = PEG_RADIUS * 1.5 if p_type == 'boss' else PEG_RADIUS
    pygame.draw.circle(surface, color, (int(x), int(y)), int(rad)); pygame.draw.circle(surface, BLACK, (int(x), int(y)), int(rad), 1) 
    if p_type == 'bomb': pygame.draw.circle(surface, RED, (int(x), int(y)), int(rad*0.4))
    elif p_type in ['prestige', 'stat', 'boss']: pygame.draw.circle(surface, WHITE, (int(x), int(y)), int(rad*0.8), 2)
    elif p_type == 'rainbow': pygame.draw.circle(surface, WHITE, (int(x), int(y)), int(rad*0.7), 2)
    else: pygame.draw.circle(surface, WHITE, (int(x), int(y)), int(rad*0.7), 1)
    pygame.draw.circle(surface, WHITE, (int(x - rad*0.35), int(y - rad*0.35)), max(2, int(rad*0.2))) 
    if p_type == 'boss':
        hp_txt = font_tiny.render(str(hp), True, WHITE); surface.blit(hp_txt, (x - hp_txt.get_width()//2, y - hp_txt.get_height()//2))
    elif p_type == 'random':
        q_txt = font_tiny.render("?", True, BLACK); surface.blit(q_txt, (x - q_txt.get_width()//2, y - q_txt.get_height()//2))

def send_to_gas(payload):
    try:
        req = urllib.request.Request(GAS_WEB_APP_URL, data=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json'})
        return json.loads(urllib.request.urlopen(req, timeout=10).read().decode('utf-8'))
    except Exception as e: return {"success": False, "message": f"Network Error: {str(e)}"}

def get_save_data_dict():
    return {'cash': cash, 'prestige_points': prestige_points, 'stat_points': stat_points, 'equipped_ball': equipped_ball, 'equipped_abilities': equipped_abilities, 'ability_inventory': ability_inventory, 'boards_cleared': boards_cleared, 'ball_stats': ball_stats, 'p_upgrades': p_upgrades, 'custom_maps_unlocked': custom_maps_unlocked, 'last_save_time': time.time()}

def apply_save_data(data):
    global cash, prestige_points, stat_points, equipped_ball, equipped_abilities, ability_inventory, boards_cleared, ball_stats, p_upgrades, last_save_time, custom_maps_unlocked
    cash = data.get('cash', cash); prestige_points = data.get('prestige_points', prestige_points); stat_points = data.get('stat_points', stat_points); equipped_ball = data.get('equipped_ball', equipped_ball); custom_maps_unlocked = data.get('custom_maps_unlocked', False)
    for k in ability_inventory.keys(): ability_inventory[k] = data.get('ability_inventory', {}).get(k, 0)
    equipped_abilities = data.get('equipped_abilities', equipped_abilities); boards_cleared = data.get('boards_cleared', boards_cleared); last_save_time = data.get('last_save_time', time.time())
    for k in p_upgrades.keys(): p_upgrades[k] = data.get('p_upgrades', {}).get(k, 0)
    for k, v in data.get('ball_stats', {}).items():
        if k in ball_stats: ball_stats[k].update(v)

def save_game(sync=False):
    data = get_save_data_dict()
    with open(SAVE_FILE, 'w') as f: json.dump(data, f)
    if current_user and current_pass:
        payload = {"action": "save", "username": current_user, "password": current_pass, "saveData": json.dumps(data)}
        if sync: send_to_gas(payload)
        else: threading.Thread(target=send_to_gas, args=(payload,), daemon=True).start()

def fetch_maps_from_cloud():
    global approved_maps_list, pending_maps_list, state
    res = send_to_gas({"action": "get_maps", "username": current_user, "password": current_pass})
    if res.get("success"):
        approved_maps_list = res.get("approved", []); pending_maps_list = res.get("pending", [])
    if state == "ADMIN_PANEL_LOADING": state = "ADMIN_PANEL"

def check_for_gifts_thread():
    global cash, gift_popup_msg
    if not current_user: return
    try:
        res = send_to_gas({"action": "check_gifts", "username": current_user, "password": current_pass})
        if res.get("success") and res.get("gifts"):
            total = 0
            for g in res["gifts"]:
                try: total += int(g.get("amount", 0))
                except: pass
                
            if total > 0:
                cash += total
                gift_popup_msg = f"The Admin has sent you ${total}!"
                save_game(sync=True)
    except Exception as e:
        print("Gift Check Failed:", e)

def auth_thread(action, username, password):
    global auth_message, is_authenticating, state, current_user, current_pass
    saveDataStr = "{}"
    if action == "register":
        if os.path.exists(SAVE_FILE):
            with open(SAVE_FILE, 'r') as f: apply_save_data(json.load(f))
        saveDataStr = json.dumps(get_save_data_dict())
    res = send_to_gas({"action": action, "username": username, "password": password, "saveData": saveDataStr})
    if res.get("success"):
        current_user = username; current_pass = password
        try:
            with open(SETTINGS_FILE, 'w') as f: json.dump({"username": username, "password": password}, f)
        except: pass
        if action == "login" and res.get("saveData", "{}"):
            try: apply_save_data(json.loads(res.get("saveData", "{}")))
            except: pass
        fetch_maps_from_cloud(); check_offline_progress()
        threading.Thread(target=check_for_gifts_thread, daemon=True).start()
        if state in ["LOGIN", "AUTO_LOGIN"]: state = "PLAY"
    else:
        auth_message = res.get("message", "Unknown error")
        if os.path.exists(SETTINGS_FILE): os.remove(SETTINGS_FILE)
        if state == "AUTO_LOGIN": state = "LOGIN"
    is_authenticating = False

saved_creds = None
if os.path.exists(SETTINGS_FILE):
    try:
        with open(SETTINGS_FILE, 'r') as f: saved_creds = json.load(f)
    except: pass
if saved_creds and saved_creds.get("username") and saved_creds.get("password"):
    state = "AUTO_LOGIN"; is_authenticating = True; input_username = saved_creds["username"]; input_password = saved_creds["password"]
    threading.Thread(target=auth_thread, args=("login", input_username, input_password), daemon=True).start()

def load_local_game():
    if os.path.exists(SAVE_FILE):
        try:
            with open(SAVE_FILE, 'r') as f: apply_save_data(json.load(f))
        except: pass

def populate_pegs(coords_list):
    global pegs; pegs = []
    bomb_rate = 0.05 + (p_upgrades.get('bomb_chance', 0) * 0.02); gold_rate = 0.25 + (p_upgrades.get('gold_chance', 0) * 0.05)
    for x, y in coords_list:
        r = random.random()
        pegs.append({'x': float(x), 'y': float(y), 'type': 'bomb' if r < bomb_rate else ('gold' if r < bomb_rate + gold_rate else 'green'), 'active': True, 'on_fire': False, 'fire_timer': 0})
    indices = list(range(len(pegs))); random.shuffle(indices)
    num_stat_pegs = int(0.5 + (p_upgrades.get('stat_pegs', 0) * 0.10))
    if random.random() < ((0.5 + (p_upgrades.get('stat_pegs', 0) * 0.10)) - num_stat_pegs): num_stat_pegs += 1
    for i in range(min(num_stat_pegs, len(indices))): pegs[indices[i]]['type'] = 'stat'
    indices = indices[num_stat_pegs:]; random.shuffle(indices)
    num_rainbow = random.randint(1, 3) + p_upgrades.get('extra_rainbow', 0)
    for i in range(min(num_rainbow, len(indices))): pegs[indices[i]]['type'] = 'rainbow'
    indices = indices[num_rainbow:]; random.shuffle(indices)
    num_prestige = 1 + p_upgrades.get('extra_prestige', 0)
    for i in range(min(num_prestige, len(indices))): pegs[indices[i]]['type'] = 'prestige'
    indices = indices[num_prestige:]; random.shuffle(indices)
    for idx in indices[:min(3, len(indices))]: pegs[idx]['type'] = 'boss'; pegs[idx]['hp'] = 5 

def randomize_editor_pegs():
    global editor_pegs
    bomb_rate = 0.05 + (p_upgrades.get('bomb_chance', 0) * 0.02); gold_rate = 0.25 + (p_upgrades.get('gold_chance', 0) * 0.05)
    r_indices = [i for i, p in enumerate(editor_pegs) if p.get('is_random', False)]
    if not r_indices: return 
    for i in r_indices:
        r = random.random()
        if r < 0.03: editor_pegs[i]['type'] = 'boss'; editor_pegs[i]['hp'] = 5
        else:
            editor_pegs[i]['type'] = 'bomb' if r < bomb_rate + 0.03 else ('gold' if r < bomb_rate + gold_rate + 0.03 else 'green')
            if 'hp' in editor_pegs[i]: del editor_pegs[i]['hp']
    random.shuffle(r_indices)
    num_stat_pegs = int(0.5 + (p_upgrades.get('stat_pegs', 0) * 0.10))
    if random.random() < ((0.5 + (p_upgrades.get('stat_pegs', 0) * 0.10)) - num_stat_pegs): num_stat_pegs += 1
    for i in range(min(num_stat_pegs, len(r_indices))): editor_pegs[r_indices[i]]['type'] = 'stat'
    r_indices = r_indices[num_stat_pegs:]; random.shuffle(r_indices)
    num_rainbow = random.randint(1, 3) + p_upgrades.get('extra_rainbow', 0)
    for i in range(min(num_rainbow, len(r_indices))): editor_pegs[r_indices[i]]['type'] = 'rainbow'

def load_custom_map(map_data):
    global pegs, bumpers
    pegs = []; bumpers = []
    max_y = HEIGHT - 175 # DEADZONE FILTER
    for p in map_data.get('pegs', []):
        if 15 < p['x'] < WIDTH - 15 and 80 < p['y'] < max_y:
            p_type = 'green' if p['type'] == 'random' else p['type']
            p_dict = {'x': float(p['x']), 'y': float(p['y']), 'type': p_type, 'active': True, 'on_fire': False, 'fire_timer': 0}
            if p_type == 'boss': p_dict['hp'] = 5
            pegs.append(p_dict)
    for b in map_data.get('bumpers', []):
        if b['radius'] < b['x'] < WIDTH - b['radius'] and 80 < b['y'] < max_y:
            bumpers.append({'x': float(b['x']), 'y': float(b['y']), 'radius': float(b['radius'])})
    return len(pegs) > 0

def l_classic(): return [(c*40 + (20 if r%2!=0 else 0) + 40, 150 + r*35) for r in range(14) for c in range(int(WIDTH/40)) if 24 < c*40+40 < WIDTH-24]
def l_triangle(): return [(c*40 + WIDTH//2 - r*20, 150 + r*35) for r in range(12) for c in range(r+1)]
def l_diamond(): return [(c*40 + WIDTH//2 - r*20, 150 + r*35) for r in range(7) for c in range(r+1)] + [(c*40 + WIDTH//2 - r*20, 150 + (12-r)*35) for r in range(6) for c in range(r+1)]

def create_random_board():
    global bumpers, lightnings, clouds, black_holes, lasers
    bumpers.clear(); lightnings.clear(); clouds.clear(); black_holes.clear(); lasers.clear()
    loaded = False
    if approved_maps_list and random.random() < 0.3: 
        loaded = load_custom_map(random.choice(approved_maps_list))
    if not loaded: 
        populate_pegs(random.choice([l_classic, l_triangle, l_diamond])())

if not pegs: create_random_board()

def get_auto_drop_rate(lvl): return [0, 2.0, 1.0, 0.5, 0.2][lvl] if lvl < 5 else 0.2

def check_offline_progress():
    global state, offline_rewards, anim_cash, anim_pp, anim_sp, last_save_time, boards_cleared
    delta = time.time() - last_save_time
    if delta > 60: 
        b_stat = ball_stats[equipped_ball]
        if b_stat['unlocked'] and b_stat['auto_drop_lvl'] > 0 and b_stat.get('auto_enabled', True):
            rate = get_auto_drop_rate(b_stat['auto_drop_lvl'])
            if rate > 0:
                total_drops = min(5000, int(delta / rate))
                multiplier = max(1, int((delta / rate) // 5000)) if (delta / rate) > 5000 else 1
                sim_cash, sim_pp, sim_sp = 0, 0, 0
                for _ in range(total_drops):
                    active_pegs = [p for p in pegs if p['active']]
                    if not active_pegs: boards_cleared += 1 * multiplier; sim_cash += 100; create_random_board(); active_pegs = [p for p in pegs if p['active']]
                    hit_pegs = random.sample(active_pegs, random.randint(1, min(6, len(active_pegs))))
                    for peg in hit_pegs:
                        peg['active'] = False
                        if peg['type'] == 'prestige': sim_pp += 3
                        elif peg['type'] == 'stat': sim_sp += 1
                        elif peg['type'] == 'boss': sim_cash += int(500 * b_stat['gold_mult'])
                        else:
                            bv = 10 if peg['type'] == 'gold' else (5 if peg['type'] in ['bomb', 'rainbow'] else 0)
                            if bv > 0: sim_cash += int(bv * b_stat['gold_mult'])
                    if equipped_ball == "Regular": sim_cash += 5 * random.randint(1, 3)
                    elif equipped_ball == "Wood": sim_cash += int(10 * b_stat['gold_mult']) * random.randint(1, 2)
                sim_cash *= multiplier; sim_pp *= multiplier; sim_sp *= multiplier
                if sim_cash > 0 or sim_pp > 0 or sim_sp > 0:
                    offline_rewards = {'cash': sim_cash, 'pp': sim_pp, 'sp': sim_sp, 'time': int(delta)}
                    anim_cash = 0.0; anim_pp = 0.0; anim_sp = 0.0; state = "OFFLINE_SCREEN"

def perform_prestige_reset():
    global cash, stat_points, ball_stats, equipped_ball, equipped_abilities, active_ability_mode, balls, boards_cleared, particles, lightnings, clouds, black_holes, lasers, drones, fire_cursor_timer, vacuum_cursor_timer
    cash = p_upgrades['starter_cash'] * 1000; boards_cleared = 0; equipped_ball = "Regular"; equipped_abilities = []; active_ability_mode = None
    fire_cursor_timer = 0; vacuum_cursor_timer = 0
    balls.clear(); particles.clear(); lightnings.clear(); clouds.clear(); black_holes.clear(); lasers.clear(); drones.clear()
    for b_stat in ball_stats.values():
        stat_points += (b_stat.get('base_top_revives', 0) * (b_stat.get('base_top_revives', 0) + 1)) // 2
        stat_points += (b_stat.get('base_bounce_revives', 0) * (b_stat.get('base_bounce_revives', 0) + 1)) // 2
    ball_stats = {name: get_default_ball_stats(unlocked=(name=="Regular")) for name in BALL_TYPES.keys()}
    create_random_board(); save_game()

def perform_data_nuke():
    global cash, prestige_points, stat_points, boards_cleared, equipped_ball, ability_inventory, equipped_abilities, active_ability_mode, p_upgrades, ball_stats, custom_maps_unlocked, fire_cursor_timer, vacuum_cursor_timer, balls, particles, lightnings, clouds, black_holes, lasers, drones
    cash = 0; prestige_points = 0; stat_points = 0; boards_cleared = 0
    equipped_ball = "Regular"; ability_inventory = {k: 0 for k in ABILITIES.keys()}; equipped_abilities = []; active_ability_mode = None
    p_upgrades = {k: 0 for k in PRESTIGE_DEFS.keys()}; custom_maps_unlocked = False
    ball_stats = {name: get_default_ball_stats(unlocked=(name=="Regular")) for name in BALL_TYPES.keys()}
    fire_cursor_timer = 0; vacuum_cursor_timer = 0
    balls.clear(); particles.clear(); lightnings.clear(); clouds.clear(); black_holes.clear(); lasers.clear(); drones.clear()
    create_random_board(); save_game(sync=True)

def generate_tree_nodes():
    nodes = []; center = (WIDTH//2, HEIGHT//2 + 30)
    branches = [('starter_cash', GREEN), ('extra_rainbow', CYAN), ('bomb_chance', ORANGE), ('extra_prestige', BROWN), ('gold_chance', GOLD), ('multishot', PURPLE), ('stat_pegs', WHITE)]
    for i, (key, color) in enumerate(branches):
        angle = i * (2 * math.pi / 7) - math.pi / 2; data = PRESTIGE_DEFS[key]; prev_pos = center
        for lvl in range(1, data['max_lvl'] + 1):
            dist = 50 + (lvl - 1) * (40 if data['max_lvl'] <= 5 else 25); x = center[0] + math.cos(angle) * dist; y = center[1] + math.sin(angle) * dist
            nodes.append({'key': key, 'level': lvl, 'x': x, 'y': y, 'prev_x': prev_pos[0], 'prev_y': prev_pos[1], 'color': color, 'cost': data['base_cost'] * lvl})
            prev_pos = (x, y)
    return center, nodes

tree_center, tree_nodes = generate_tree_nodes()

def spawn_particles(x, y, color, count=15, speed=4.0):
    for _ in range(count): particles.append({'x': x, 'y': y, 'vx': random.uniform(-speed, speed), 'vy': random.uniform(-speed, speed), 'life': random.uniform(20, 40), 'color': color, 'radius': random.uniform(2, 5)})

def draw_cannon(mouse_x, mouse_y):
    dx, dy = mouse_x - CANNON_POS[0], mouse_y - CANNON_POS[1]
    angle = math.atan2(dy, dx)
    pygame.draw.circle(screen, GRAY, CANNON_POS, 25)
    pygame.draw.line(screen, GRAY, CANNON_POS, (CANNON_POS[0] + math.cos(angle) * 50, CANNON_POS[1] + math.sin(angle) * 50), 20)
    return angle, CANNON_POS[0] + math.cos(angle) * 50, CANNON_POS[1] + math.sin(angle) * 50

def spawn_ball(ball_type, x, y, vx, vy, is_manual=False, inherited_mult=None):
    b = BALL_TYPES[ball_type]; stats = ball_stats[ball_type] if ball_type in ball_stats else ball_stats["Regular"]
    revive_stack = []
    if random.random() < 0.40:
        revive_stack.extend(['top'] * stats.get('base_top_revives', 0)); revive_stack.extend(['bounce'] * stats.get('base_bounce_revives', 0)); random.shuffle(revive_stack)
    b_dict = {'type': ball_type, 'is_manual': is_manual, 'x': x, 'y': y, 'vx': vx, 'vy': vy, 'color': b['color'], 'grav': b['base_grav'], 'bounce': min(0.98, b['base_bounce'] + stats['bounce_bonus']), 'radius': 4 if ball_type == "Shrapnel" else BALL_RADIUS, 'gold_mult': inherited_mult if inherited_mult else stats['gold_mult'], 'revive_stack': revive_stack}
    if ball_type == 'Magic': b_dict.update({'lightning_strikes': 2, 'lightning_timer': FPS * 1.5, 'vy': 0.0})
    elif ball_type == 'Taco': b_dict.update({'max_hits': random.randint(2, 4), 'hits_taken': 0, 'radius': 14})
    balls.append(b_dict)

def grant_peg_reward(peg, gold_mult, is_direct_hit=True, b_type=None):
    global cash, prestige_points, stat_points
    if is_playtest: gold_mult *= 0.01 
    if peg['type'] == 'prestige':
        if not is_playtest: prestige_points += 3
        spawn_particles(peg['x'], peg['y'], BRONZE, count=20, speed=5.0)
    elif peg['type'] == 'stat':
        if not is_playtest: stat_points += 1
        spawn_particles(peg['x'], peg['y'], CYAN, count=30, speed=6.0)
    elif peg['type'] == 'boss':
        cash += int(500 * gold_mult); spawn_particles(peg['x'], peg['y'], MAGENTA, count=40, speed=8.0)
    else:
        bv = 10 if peg['type'] == 'gold' else (5 if peg['type'] in ['bomb', 'rainbow'] else 0)
        if bv > 0: cash += int(bv * gold_mult)
        
    if is_direct_hit:
        if peg['type'] == 'bomb':
            spawn_particles(peg['x'], peg['y'], ORANGE, count=20, speed=6.0)
            for _ in range(3): spawn_ball(b_type if b_type != 'Shrapnel' else 'Regular', peg['x'], peg['y'], random.uniform(-6, 6), random.uniform(-6, -2))
        if peg['type'] == 'rainbow':
            spawn_particles(peg['x'], peg['y'], get_rainbow_color(), count=30, speed=8.0)
            event_roll = random.randint(1, 3)
            if event_roll == 1: 
                for p in pegs:
                    if p['active'] and p['type'] == 'green' and random.random() < 0.5: p['type'] = 'gold'
            elif event_roll == 2: 
                for _ in range(5): spawn_ball(b_type if b_type != 'Shrapnel' else 'Regular', peg['x'], peg['y'], random.uniform(-8, 8), random.uniform(-8, -2))
            elif event_roll == 3: cash += int(500 * gold_mult)

def roll_crate(crate_name):
    crate = CRATES[crate_name]; results = []
    for _ in range(crate['rolls']):
        r = random.random(); rarity = 'Legendary' if r < crate['odds']['Legendary'] else ('Epic' if r < crate['odds']['Legendary']+crate['odds']['Epic'] else ('Rare' if r < crate['odds']['Legendary']+crate['odds']['Epic']+crate['odds']['Rare'] else 'Common'))
        chosen = random.choice([k for k,v in ABILITIES.items() if v['rarity'] == rarity])
        ability_inventory[chosen] += 1; results.append({"name": chosen, "rarity": rarity})
    return results

def upload_map_thread(map_data):
    global is_uploading, upload_message, state, editor_pegs, editor_bumpers
    res = send_to_gas({"action": "upload_map", "username": current_user, "password": current_pass, "mapData": map_data})
    upload_message = "Upload Successful!" if res.get("success") else "Upload Failed: " + res.get("message", "")
    time.sleep(1.5)
    if res.get("success"):
        editor_pegs = []; editor_bumpers = []; state = "MENU"
    is_uploading = False; upload_message = ""

def draw_main_menu():
    screen.fill(BLACK); menu_w, menu_h = 1000, 600; m_x, m_y = WIDTH//2 - menu_w//2, HEIGHT//2 - menu_h//2
    pygame.draw.rect(screen, (30, 20, 10), (m_x-5, m_y-5, menu_w+10, menu_h+10), border_radius=15)
    pygame.draw.rect(screen, BROWN, (m_x, m_y, menu_w, menu_h), border_radius=10); pygame.draw.rect(screen, GOLD, (m_x, m_y, menu_w, menu_h), 3, border_radius=10)
    
    btn_out = pygame.Rect(m_x + 20, m_y + 20, 100, 40); draw_btn(screen, btn_out, RED, "Logout", font_med, WHITE)
    btn_adm = pygame.Rect(m_x + 130, m_y + 20, 160, 40) if current_user == "DaniBoyNov2014" else None
    if btn_adm: draw_btn(screen, btn_adm, MAGENTA, "Admin Panel", font_med, WHITE)

    screen.blit(font_large.render(f"Cash: ${cash}", True, GREEN), (m_x + 350, m_y + 25))

    stats = ball_stats[equipped_ball]
    pygame.draw.rect(screen, TAN, (m_x + 30, m_y + 80, menu_w - 60, 110), border_radius=5); pygame.draw.rect(screen, BLACK, (m_x + 30, m_y + 80, menu_w - 60, 110), 2, border_radius=5)
    screen.blit(font_large.render(f"[{equipped_ball}] Lvl {stats['level']}", True, BLACK), (m_x + 50, m_y + 90))
    screen.blit(font_med.render(f"GOLD: x{stats['gold_mult']:.1f}  AMMO: {stats['max_balls']}", True, BLACK), (m_x + 50, m_y + 130))
    
    btn_pow = pygame.Rect(m_x + 400, m_y + 90, 250, 40); draw_btn(screen, btn_pow, GREEN if cash >= stats['upg_cost_power'] else GRAY, f"Upg Power (${stats['upg_cost_power']})", font_med, BLACK)
    btn_cap = pygame.Rect(m_x + 400, m_y + 140, 250, 40); draw_btn(screen, btn_cap, GREEN if cash >= stats['upg_cost_balls'] else GRAY, f"Upg Ammo (${stats['upg_cost_balls']})", font_med, BLACK)
    btn_auto = pygame.Rect(m_x + 670, m_y + 140, 250, 40)
    if stats['auto_drop_lvl'] >= 4: draw_btn(screen, btn_auto, GOLD, "Auto: MAXED", font_med, BLACK)
    else: draw_btn(screen, btn_auto, GREEN if cash >= stats['upg_cost_auto'] else GRAY, f"Upg Auto (${stats['upg_cost_auto']})", font_med, BLACK)

    btn_spec = None; btn_top = None; btn_bot = None
    if not stats.get('special_unlocked'):
        btn_spec = pygame.Rect(m_x + 680, m_y + 90, 230, 30); draw_btn(screen, btn_spec, PURPLE if cash >= 20000 else GRAY, "Unlock Special ($20k)", font_small, WHITE)
    else:
        top_lv = stats.get('base_top_revives', 0); bot_lv = stats.get('base_bounce_revives', 0)
        screen.blit(font_small.render(f"Top Rev: {top_lv}/5", True, DARK_BLUE), (m_x + 680, m_y + 95)); btn_top = pygame.Rect(m_x + 790, m_y + 90, 60, 25); draw_btn(screen, btn_top, CYAN if stat_points >= top_lv+1 else GRAY, f"{top_lv+1} SP", font_small, BLACK)
        screen.blit(font_small.render(f"Bot Rev: {bot_lv}/5", True, DARK_BLUE), (m_x + 680, m_y + 120)); btn_bot = pygame.Rect(m_x + 790, m_y + 115, 60, 25); draw_btn(screen, btn_bot, GREEN if stat_points >= bot_lv+1 else GRAY, f"{bot_lv+1} SP", font_small, BLACK)
        
    c_rects = {}; start_x = m_x + (menu_w - (5 * 145)) // 2 + 10; start_y = m_y + 240
    for i, (b_name, b_data) in enumerate({k: v for k, v in BALL_TYPES.items() if not v.get('hidden')}.items()):
        card = pygame.Rect(start_x + ((i % 5) * 145), start_y + ((i // 5) * 135), 135, 125); c_rects[b_name] = card
        pygame.draw.rect(screen, TAN, card, border_radius=5); pygame.draw.rect(screen, GOLD if equipped_ball == b_name else BLACK, card, 3, border_radius=5)
        if b_name == "Taco": pygame.draw.circle(screen, GOLD, (card.x+67, card.y+25), 15); pygame.draw.rect(screen, BROWN, (card.x+54, card.y+23, 26, 6)); pygame.draw.rect(screen, GREEN, (card.x+56, card.y+19, 22, 4))
        else: pygame.draw.circle(screen, b_data['color'], (card.x + 67, card.y + 25), 15); pygame.draw.circle(screen, WHITE, (card.x + 62, card.y + 20), 4)
        screen.blit(font_small.render(b_name, True, BLACK), (card.x + 10, card.y + 50))
        if ball_stats[b_name]['unlocked']: screen.blit(font_small.render("EQUIPPED" if equipped_ball == b_name else "EQUIP", True, GREEN), (card.x + 15, card.y + 100))
        else: screen.blit(font_small.render(f"${b_data['cost']//1000000}M" if b_data['cost'] >= 1000000 else f"${b_data['cost']}", True, RED), (card.x + 15, card.y + 100))

    btn_cust = pygame.Rect(m_x + 30, m_y + menu_h - 110, 250, 40); draw_btn(screen, btn_cust, DARK_BLUE if custom_maps_unlocked else GRAY, "Custom Maps" if custom_maps_unlocked else "Unlock Maps ($1M)", font_med, WHITE if custom_maps_unlocked else BLACK)
    btn_del = pygame.Rect(m_x + 300, m_y + menu_h - 110, 280, 40); draw_btn(screen, btn_del, MAROON, "DELETE SAVE DATA", font_med, WHITE)
    btn_tree = pygame.Rect(m_x + 30, m_y + menu_h - 60, 250, 40); draw_btn(screen, btn_tree, PURPLE, "View Prestige Tree", font_med, WHITE)
    btn_pres = pygame.Rect(m_x + 300, m_y + menu_h - 60, 280, 40); draw_btn(screen, btn_pres, BRONZE, "PRESTIGE & RESTART", font_med, BLACK)
    btn_abil = pygame.Rect(m_x + 600, m_y + menu_h - 60, 180, 40); draw_btn(screen, btn_abil, LIGHT_BLUE, "Abilities", font_med, BLACK)
    btn_cls = pygame.Rect(m_x + menu_w - 110, m_y + menu_h - 60, 80, 40); draw_btn(screen, btn_cls, RED, "Back", font_med, WHITE)
    return btn_pow, btn_cap, btn_auto, btn_cls, c_rects, btn_tree, btn_pres, btn_abil, btn_cust, btn_adm, btn_spec, btn_top, btn_bot, btn_out, btn_del

running = True
while running:
    mx, my = pygame.mouse.get_pos()
    active_pegs = [p for p in pegs if p['active']]
    
    for event in pygame.event.get():
        if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
            if state not in ["LOGIN", "AUTO_LOGIN"]: save_game(sync=True)
            running = False
            
        elif event.type == pygame.KEYDOWN:
            if state == "ADMIN_PANEL":
                if admin_active_input == "user":
                    if event.key == pygame.K_BACKSPACE: admin_input_user = admin_input_user[:-1]
                    else: admin_input_user += event.unicode
                elif admin_active_input == "amount":
                    if event.key == pygame.K_BACKSPACE: admin_input_amount = admin_input_amount[:-1]
                    elif event.unicode.isdigit() or (event.unicode == "-" and len(admin_input_amount) == 0): admin_input_amount += event.unicode
            elif state == "LOGIN" and not is_authenticating:
                if active_input == "username":
                    if event.key == pygame.K_BACKSPACE: input_username = input_username[:-1]
                    elif event.key not in [pygame.K_RETURN, pygame.K_TAB]: input_username += event.unicode
                elif active_input == "password":
                    if event.key == pygame.K_BACKSPACE: input_password = input_password[:-1]
                    elif event.key not in [pygame.K_RETURN, pygame.K_TAB]: input_password += event.unicode
            
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if state == "LOGIN":
                u_box = pygame.Rect(WIDTH//2 - 150, HEIGHT//2 - 80, 300, 40); p_box = pygame.Rect(WIDTH//2 - 150, HEIGHT//2 - 10, 300, 40)
                btn_log = pygame.Rect(WIDTH//2 - 150, HEIGHT//2 + 60, 140, 40); btn_reg = pygame.Rect(WIDTH//2 + 10, HEIGHT//2 + 60, 140, 40); btn_off = pygame.Rect(WIDTH//2 - 100, HEIGHT//2 + 120, 200, 40)
                if not is_authenticating:
                    if u_box.collidepoint(mx, my): active_input = "username"
                    elif p_box.collidepoint(mx, my): active_input = "password"
                    elif btn_log.collidepoint(mx, my) and input_username and input_password:
                        is_authenticating = True; auth_message = "Logging in..."; threading.Thread(target=auth_thread, args=("login", input_username, input_password), daemon=True).start()
                    elif btn_reg.collidepoint(mx, my) and input_username and input_password:
                        is_authenticating = True; auth_message = "Creating Account..."; threading.Thread(target=auth_thread, args=("register", input_username, input_password), daemon=True).start()
                    elif btn_off.collidepoint(mx, my): load_local_game(); check_offline_progress(); state = "PLAY"
                    
            elif state == "ADMIN_PANEL":
                r_user = pygame.Rect(50, HEIGHT - 100, 200, 40); r_amt = pygame.Rect(260, HEIGHT - 100, 150, 40); r_btn = pygame.Rect(420, HEIGHT - 100, 120, 40)
                if pygame.Rect(WIDTH - 120, 20, 100, 40).collidepoint(mx, my): state = "MENU"
                elif r_user.collidepoint(mx, my): admin_active_input = "user"
                elif r_amt.collidepoint(mx, my): admin_active_input = "amount"
                elif r_btn.collidepoint(mx, my):
                    if admin_input_user.strip() and admin_input_amount.strip() not in ["", "-"]:
                        res = send_to_gas({"action": "give_money", "username": current_user, "password": current_pass, "targetUser": admin_input_user.strip(), "amount": admin_input_amount.strip()})
                        admin_msg = res.get("message", "")
                        admin_input_user = ""; admin_input_amount = ""
                    else: admin_msg = "Invalid input!"
                else:
                    for i, p_map in enumerate(pending_maps_list):
                        y_pos = 100 + (i * 50)
                        if pygame.Rect(WIDTH - 540, y_pos, 100, 40).collidepoint(mx, my):
                            p_map['unfair'] = not p_map.get('unfair', False); break
                        elif pygame.Rect(WIDTH - 300, y_pos, 100, 40).collidepoint(mx, my):
                            res = send_to_gas({"action": "moderate_map", "username": current_user, "password": current_pass, "mapIndex": i, "modAction": "approve", "setUnfair": p_map.get('unfair', False)})
                            if res.get("success"): pending_maps_list = res.get("pending", [])
                            break
                        elif pygame.Rect(WIDTH - 180, y_pos, 100, 40).collidepoint(mx, my):
                            res = send_to_gas({"action": "moderate_map", "username": current_user, "password": current_pass, "mapIndex": i, "modAction": "reject"})
                            if res.get("success"): pending_maps_list = res.get("pending", [])
                            break
                        elif pygame.Rect(WIDTH - 420, y_pos, 100, 40).collidepoint(mx, my):
                            backup_pegs = copy.deepcopy(pegs); backup_bumpers = copy.deepcopy(bumpers); backup_cash = cash
                            load_custom_map(p_map); is_playtest = True; state = "PLAY"; break
                            
            elif state == "MAP_EDITOR" and not is_uploading:
                clicked_ui = False
                if pygame.Rect(WIDTH - 120, 20, 100, 40).collidepoint(mx, my): state = "MENU"; clicked_ui = True
                elif pygame.Rect(WIDTH//2 - 150, 20, 140, 40).collidepoint(mx, my):
                    backup_pegs = copy.deepcopy(pegs); backup_bumpers = copy.deepcopy(bumpers); backup_cash = cash
                    pegs = copy.deepcopy(editor_pegs); bumpers = copy.deepcopy(editor_bumpers); is_playtest = True; state = "PLAY"; clicked_ui = True
                elif pygame.Rect(WIDTH//2 + 10, 20, 140, 40).collidepoint(mx, my):
                    is_uploading = True; threading.Thread(target=upload_map_thread, args=({"author": current_user, "unfair": editor_is_unfair, "pegs": editor_pegs, "bumpers": editor_bumpers},), daemon=True).start(); clicked_ui = True
                elif pygame.Rect(WIDTH//2 - 310, 20, 140, 40).collidepoint(mx, my): randomize_editor_pegs(); clicked_ui = True
                elif pygame.Rect(WIDTH//2 + 170, 20, 150, 40).collidepoint(mx, my): editor_is_unfair = not editor_is_unfair; clicked_ui = True
                elif pygame.Rect(WIDTH - 250, 20, 110, 40).collidepoint(mx, my): editor_snap = not editor_snap; clicked_ui = True
                    
                for i, t in enumerate(['green', 'gold', 'bomb', 'rainbow', 'stat', 'boss', 'random', 'bumper']):
                    if pygame.Rect(20, 100 + i*50, 40, 40).collidepoint(mx, my): editor_tool = t; clicked_ui = True

            elif state == "PLAY" and board_clear_timer == 0:
                clicked_ui = False
                if is_playtest:
                    if pygame.Rect(WIDTH//2 - 100, 20, 200, 50).collidepoint(mx, my):
                        cash = backup_cash + int(max(0, cash - backup_cash) * 0.01); pegs = copy.deepcopy(backup_pegs); bumpers = copy.deepcopy(backup_bumpers)
                        balls.clear(); particles.clear(); is_playtest = False; state = "MAP_EDITOR" if current_user != "DaniBoyNov2014" else "ADMIN_PANEL"; clicked_ui = True
                else:
                    if WIDTH - 120 <= mx <= WIDTH - 20 and 20 <= my <= 60:
                        state = "MENU"; clicked_ui = True
                        threading.Thread(target=check_for_gifts_thread, daemon=True).start() 
                        
                    if not clicked_ui:
                        auto_y = 70
                        for b_name, b_stat in ball_stats.items():
                            if b_stat['auto_drop_lvl'] > 0:
                                if pygame.Rect(WIDTH - 150, auto_y, 130, 35).collidepoint(mx, my): b_stat['auto_enabled'] = not b_stat.get('auto_enabled', True); save_game(); clicked_ui = True; break
                                auto_y += 45
                                
                if equipped_abilities and not clicked_ui:
                    for i, a_name in enumerate(equipped_abilities):
                        if pygame.Rect(20, HEIGHT - 70 - (i * 60), 290, 50).collidepoint(mx, my):
                            clicked_ui = True; active_ability_mode = None if active_ability_mode == a_name else (a_name if ability_inventory.get(a_name, 0) > 0 else active_ability_mode)
                            break
                            
                if active_ability_mode and not clicked_ui and my > 80:
                    if ability_inventory.get(active_ability_mode, 0) > 0:
                        ability_inventory[active_ability_mode] -= 1
                        
                        # --- FULLY IMPLEMENTED ABILITIES ---
                        if active_ability_mode == "Midas Touch":
                            for p in pegs:
                                if p['active'] and math.hypot(p['x']-mx, p['y']-my) < 150: p['type'] = 'gold'
                        elif active_ability_mode == "Starfall":
                            for _ in range(10): spawn_ball('Bouncy', mx + random.uniform(-50,50), my, random.uniform(-5,5), 0)
                        elif active_ability_mode == "Bounce Revive":
                            for b in balls: b['revive_stack'].append('bounce')
                        elif active_ability_mode == "Thunder Cloud":
                            for _ in range(5):
                                active_p = [p for p in pegs if p['active']]
                                if active_p: 
                                    rp = random.choice(active_p); rp['active'] = False; grant_peg_reward(rp, 1.0, True, 'Regular')
                                    spawn_particles(rp['x'], rp['y'], YELLOW, 20, 5)
                        elif active_ability_mode == "Revive Wave":
                            for b in balls: b['y'] = 50; b['vy'] = 0
                        elif active_ability_mode == "Black Hole":
                            black_holes.append({'x': mx, 'y': my, 'life': FPS * 6, 'radius': 150})
                        elif active_ability_mode == "Orbital Strike":
                            lasers.append({'x': mx, 'life': FPS})
                            for p in pegs:
                                if p['active'] and abs(p['x'] - mx) < 60:
                                    p['active'] = False; grant_peg_reward(p, 1.0, True, 'Regular')
                        elif active_ability_mode == "Drone":
                            drones.append({'x': mx, 'y': my, 'balls_left': 10, 'timer': 0})
                        elif active_ability_mode == "Fire Cursor":
                            fire_cursor_timer = FPS * 5
                        elif active_ability_mode == "Vacuum Cursor":
                            vacuum_cursor_timer = FPS * 5
                            
                        active_ability_mode = None; save_game(); clicked_ui = True
                    else: active_ability_mode = None # Just unequip if they click with 0 tokens
                
                if not clicked_ui:
                    if len([b for b in balls if b['is_manual'] and b['type'] == equipped_ball]) < ball_stats[equipped_ball]['max_balls'] and my > 70: 
                        angle, spawn_x, spawn_y = draw_cannon(mx, my)
                        if math.sin(angle) > 0: 
                            shots = 1 + p_upgrades.get('multishot', 0)
                            for s in range(shots): spawn_ball(equipped_ball, spawn_x, spawn_y, math.cos(angle + (s - (shots-1)/2.0)*0.15)*10, math.sin(angle + (s - (shots-1)/2.0)*0.15)*10, is_manual=True)

            elif state == "MENU":
                if gift_popup_msg:
                    if pygame.Rect(WIDTH//2 - 75, HEIGHT//2 + 50, 150, 40).collidepoint(mx, my): gift_popup_msg = ""
                    continue

                btn_pow, btn_cap, btn_auto, btn_cls, c_rects, btn_tree, btn_pres, btn_abil, btn_cust, btn_adm, btn_spec, btn_top, btn_bot, btn_out, btn_del = draw_main_menu()
                stats = ball_stats[equipped_ball]
                
                if btn_out.collidepoint(mx, my): save_game(sync=True); clear_local_settings(); current_user = ""; current_pass = ""; input_password = ""; state = "LOGIN"
                elif btn_adm and btn_adm.collidepoint(mx, my): state = "ADMIN_PANEL_LOADING"; threading.Thread(target=fetch_maps_from_cloud, daemon=True).start()
                elif btn_cls.collidepoint(mx, my): state = "PLAY"; save_game()
                elif btn_cust.collidepoint(mx, my):
                    if custom_maps_unlocked: state = "MAP_EDITOR"
                    elif cash >= 1000000: cash -= 1000000; custom_maps_unlocked = True; save_game()
                elif btn_del.collidepoint(mx, my): state = "CONFIRM_DELETE"
                elif btn_tree.collidepoint(mx, my): state = "PRESTIGE_TREE"; view_only_tree = True 
                elif btn_pres.collidepoint(mx, my): state = "CONFIRM_PRESTIGE"
                elif btn_abil.collidepoint(mx, my): state = "ABILITIES_MENU"
                elif btn_pow.collidepoint(mx, my) and cash >= stats['upg_cost_power']:
                    cash -= stats['upg_cost_power']; stats['level'] += 1; stats['gold_mult'] += 0.5; stats['bounce_bonus'] += 0.02; stats['upg_cost_power'] = int(stats['upg_cost_power'] * 1.5)
                elif btn_cap.collidepoint(mx, my) and cash >= stats['upg_cost_balls']:
                    cash -= stats['upg_cost_balls']; stats['max_balls'] += 1; stats['upg_cost_balls'] = int(stats['upg_cost_balls'] * 2.5)
                elif btn_auto.collidepoint(mx, my) and cash >= stats['upg_cost_auto'] and stats['auto_drop_lvl'] < 4:
                    cash -= stats['upg_cost_auto']; stats['auto_drop_lvl'] += 1; stats['upg_cost_auto'] = int(stats['upg_cost_auto'] * 3.0)
                elif btn_spec and btn_spec.collidepoint(mx, my) and cash >= 20000: cash -= 20000; stats['special_unlocked'] = True; save_game()
                elif btn_top and btn_top.collidepoint(mx, my) and stat_points >= stats.get('base_top_revives',0)+1 and stats.get('base_top_revives',0) < 5:
                    stat_points -= stats.get('base_top_revives',0) + 1; stats['base_top_revives'] = stats.get('base_top_revives',0) + 1; save_game()
                elif btn_bot and btn_bot.collidepoint(mx, my) and stat_points >= stats.get('base_bounce_revives',0)+1 and stats.get('base_bounce_revives',0) < 5:
                    stat_points -= stats.get('base_bounce_revives',0) + 1; stats['base_bounce_revives'] = stats.get('base_bounce_revives',0) + 1; save_game()
                    
                for b_name, rect in c_rects.items():
                    if rect.collidepoint(mx, my):
                        if ball_stats[b_name]['unlocked']: equipped_ball = b_name
                        elif cash >= BALL_TYPES[b_name]['cost']: cash -= BALL_TYPES[b_name]['cost']; ball_stats[b_name]['unlocked'] = True; equipped_ball = b_name

            elif state == "CONFIRM_DELETE":
                if pygame.Rect(WIDTH//2 - 150, HEIGHT//2 + 50, 100, 50).collidepoint(mx, my):
                    perform_data_nuke(); state = "MENU"
                elif pygame.Rect(WIDTH//2 + 50, HEIGHT//2 + 50, 100, 50).collidepoint(mx, my): state = "MENU"

            elif state == "ABILITIES_MENU":
                screen.fill(BLACK); menu_w, menu_h = 900, 700; m_x, m_y = WIDTH//2 - menu_w//2, HEIGHT//2 - menu_h//2
                pygame.draw.rect(screen, DARK_GRAY, (m_x, m_y, menu_w, menu_h), border_radius=10); pygame.draw.rect(screen, LIGHT_BLUE, (m_x, m_y, menu_w, menu_h), 3, border_radius=10)
                screen.blit(font_large.render("--- ACTIVE ABILITIES ---", True, LIGHT_BLUE), (m_x + menu_w//2 - 200, m_y + 20)); screen.blit(font_med.render(f"Equipped: {len(equipped_abilities)} / 5", True, WHITE), (m_x + menu_w//2 - 90, m_y + 60))
                for i, (a_name, a_data) in enumerate(ABILITIES.items()):
                    card = pygame.Rect(m_x + 30 + ((i % 2) * 430), m_y + 100 + ((i // 2) * 90), 410, 80)
                    if card.collidepoint(mx, my):
                        if a_name in equipped_abilities: equipped_abilities.remove(a_name); active_ability_mode = None if active_ability_mode == a_name else active_ability_mode
                        elif len(equipped_abilities) < 5: equipped_abilities.append(a_name)
                if pygame.Rect(m_x + menu_w - 130, m_y + 20, 100, 40).collidepoint(mx, my): state = "MENU"; save_game()
                elif pygame.Rect(m_x + 30, m_y + menu_h - 60, 220, 40).collidepoint(mx, my): state = "CRATES_MENU"
                elif pygame.Rect(m_x + menu_w//2 - 100, m_y + menu_h - 60, 200, 40).collidepoint(mx, my): equipped_abilities.clear(); active_ability_mode = None

            elif state == "CRATES_MENU":
                m_x, m_y = WIDTH//2 - 500, HEIGHT//2 - 350
                if pygame.Rect(m_x + 1000//2 - 75, m_y + 700 - 70, 150, 40).collidepoint(mx, my): state = "ABILITIES_MENU"
                else:
                    for i, (c_name, c_data) in enumerate(CRATES.items()):
                        if pygame.Rect(m_x + 73 + i*293 + 30, m_y + 170 + 360, 200, 40).collidepoint(mx, my) and cash >= c_data['cost']:
                            cash -= c_data['cost']; crate_results_display = roll_crate(c_name); state = "CRATE_REWARD"

            elif state == "CRATE_REWARD":
                if pygame.Rect(WIDTH//2 - 75, HEIGHT - 150, 150, 50).collidepoint(mx, my): state = "CRATES_MENU"; save_game()

            elif state == "CONFIRM_PRESTIGE":
                if pygame.Rect(WIDTH//2 - 150, HEIGHT//2 + 20, 100, 50).collidepoint(mx, my): perform_prestige_reset(); state = "PRESTIGE_TREE"; view_only_tree = False 
                elif pygame.Rect(WIDTH//2 + 50, HEIGHT//2 + 20, 100, 50).collidepoint(mx, my): state = "MENU"

            elif state == "PRESTIGE_TREE":
                for node in tree_nodes:
                    if math.hypot(mx - node['x'], my - node['y']) <= 16 and not view_only_tree and p_upgrades.get(node['key'], 0) == node['level'] - 1 and prestige_points >= node['cost']:
                        prestige_points -= node['cost']; p_upgrades[node['key']] += 1; populate_pegs([(p['x'], p['y']) for p in pegs if p['active']])
                if pygame.Rect(WIDTH - 120, 20, 100, 40).collidepoint(mx, my): state = "MENU" if view_only_tree else "PLAY"; save_game()

            elif state == "OFFLINE_SCREEN":
                if pygame.Rect(WIDTH//2 - 100, HEIGHT - 150, 200, 60).collidepoint(mx, my):
                    cash += offline_rewards['cash']; prestige_points += offline_rewards['pp']; stat_points += offline_rewards['sp']
                    last_save_time = time.time(); save_game(); state = "PLAY"

    if state == "AUTO_LOGIN":
        screen.fill(DARK_BG); pygame.draw.rect(screen, BLACK, (WIDTH//2 - 200, HEIGHT//2 - 100, 400, 200), border_radius=15); pygame.draw.rect(screen, GOLD, (WIDTH//2 - 200, HEIGHT//2 - 100, 400, 200), 3, border_radius=15)
        screen.blit(font_large.render("Authenticating...", True, CYAN), (WIDTH//2 - 120, HEIGHT//2 - 30))

    elif state == "LOGIN":
        screen.fill(DARK_BG); pygame.draw.rect(screen, BLACK, (WIDTH//2 - 200, HEIGHT//2 - 200, 400, 400), border_radius=15); pygame.draw.rect(screen, CYAN, (WIDTH//2 - 200, HEIGHT//2 - 200, 400, 400), 3, border_radius=15)
        screen.blit(font_large.render("PEGGLE CLOUD", True, GOLD), (WIDTH//2 - 140, HEIGHT//2 - 170))
        pygame.draw.rect(screen, WHITE, pygame.Rect(WIDTH//2 - 150, HEIGHT//2 - 80, 300, 40), border_radius=5); pygame.draw.rect(screen, CYAN if active_input == "username" else GRAY, pygame.Rect(WIDTH//2 - 150, HEIGHT//2 - 80, 300, 40), 3, border_radius=5)
        screen.blit(font_med.render(input_username, True, BLACK), (WIDTH//2 - 140, HEIGHT//2 - 70))
        pygame.draw.rect(screen, WHITE, pygame.Rect(WIDTH//2 - 150, HEIGHT//2 - 10, 300, 40), border_radius=5); pygame.draw.rect(screen, CYAN if active_input == "password" else GRAY, pygame.Rect(WIDTH//2 - 150, HEIGHT//2 - 10, 300, 40), 3, border_radius=5)
        screen.blit(font_med.render("*" * len(input_password), True, BLACK), (WIDTH//2 - 140, HEIGHT//2))

        draw_btn(screen, pygame.Rect(WIDTH//2 - 150, HEIGHT//2 + 60, 140, 40), GREEN if not is_authenticating else GRAY, "Login", font_med, BLACK)
        draw_btn(screen, pygame.Rect(WIDTH//2 + 10, HEIGHT//2 + 60, 140, 40), PURPLE if not is_authenticating else GRAY, "Register", font_med, WHITE)
        draw_btn(screen, pygame.Rect(WIDTH//2 - 100, HEIGHT//2 + 120, 200, 40), DARK_GRAY if not is_authenticating else GRAY, "Play Offline", font_small, WHITE)

        if auth_message or is_authenticating:
            s_rect = pygame.Rect(WIDTH//2 - 200, HEIGHT//2 + 170, 400, 50); pygame.draw.rect(screen, BLACK, s_rect, border_radius=5)
            pygame.draw.rect(screen, GREEN if "success" in auth_message.lower() or "created" in auth_message.lower() else (CYAN if is_authenticating else RED), s_rect, 2, border_radius=5)
            msg_surf = font_small.render(auth_message if auth_message else "Connecting to Server...", True, WHITE)
            screen.blit(msg_surf, (s_rect.centerx - msg_surf.get_width()//2, s_rect.centery - msg_surf.get_height()//2))
            if is_authenticating: pygame.draw.arc(screen, CYAN, (s_rect.x + 15, s_rect.centery - 10, 20, 20), pygame.time.get_ticks() / 150.0, (pygame.time.get_ticks() / 150.0) + math.pi, 3)

    elif state == "ADMIN_PANEL_LOADING":
        screen.fill(BLACK); screen.blit(font_huge.render("FETCHING MAPS & CLOUD DATA...", True, CYAN), (WIDTH//2 - 400, HEIGHT//2))

    elif state == "ADMIN_PANEL":
        screen.fill(BLACK); screen.blit(font_huge.render("ADMIN PANEL", True, MAGENTA), (50, 20))
        draw_btn(screen, pygame.Rect(WIDTH - 120, 20, 100, 40), RED, "Back", font_med, WHITE)
        
        screen.blit(font_med.render("--- ADMIN BANK ---", True, GOLD), (50, HEIGHT - 150))
        r_user = pygame.Rect(50, HEIGHT - 100, 200, 40); r_amt = pygame.Rect(260, HEIGHT - 100, 150, 40); r_btn = pygame.Rect(420, HEIGHT - 100, 120, 40)
        pygame.draw.rect(screen, WHITE, r_user); screen.blit(font_med.render(admin_input_user or "Username", True, BLACK if admin_input_user else GRAY), (r_user.x+5, r_user.y+5)); pygame.draw.rect(screen, CYAN if admin_active_input == "user" else BLACK, r_user, 3)
        pygame.draw.rect(screen, WHITE, r_amt); screen.blit(font_med.render(admin_input_amount or "Amount", True, BLACK if admin_input_amount else GRAY), (r_amt.x+5, r_amt.y+5)); pygame.draw.rect(screen, CYAN if admin_active_input == "amount" else BLACK, r_amt, 3)
        draw_btn(screen, r_btn, GREEN, "Send", font_med, BLACK)
        if admin_msg: screen.blit(font_med.render(admin_msg, True, YELLOW), (560, HEIGHT - 90))

        screen.blit(font_med.render("--- PENDING MAPS ---", True, CYAN), (50, 80))
        for i, p_map in enumerate(pending_maps_list):
            y_pos = 120 + (i * 50); screen.blit(font_med.render(f"Author: {p_map.get('author', 'Unknown')}", True, WHITE), (50, y_pos))
            draw_btn(screen, pygame.Rect(WIDTH - 540, y_pos, 100, 40), ORANGE if p_map.get('unfair') else DARK_GRAY, "Unfair!" if p_map.get('unfair') else "Fair", font_med, BLACK)
            draw_btn(screen, pygame.Rect(WIDTH - 420, y_pos, 100, 40), CYAN, "Test", font_med, BLACK)
            draw_btn(screen, pygame.Rect(WIDTH - 300, y_pos, 100, 40), GREEN, "Approve", font_med, BLACK)
            draw_btn(screen, pygame.Rect(WIDTH - 180, y_pos, 100, 40), RED, "Reject", font_med, WHITE)

    elif state == "MAP_EDITOR":
        screen.fill(BLACK)
        max_y = HEIGHT - 175
        
        if editor_snap:
            for x in range(0, WIDTH, 25): pygame.draw.line(screen, (30, 30, 30), (x, 80), (x, max_y))
            for y in range(80, max_y, 25): pygame.draw.line(screen, (30, 30, 30), (0, y), (WIDTH, y))

        pygame.draw.line(screen, RED, (0, max_y), (WIDTH, max_y), 2)
        screen.blit(font_small.render("--- DEAD ZONE (No Pegs Allowed) ---", True, RED), (WIDTH//2 - 150, max_y + 10))

        draw_btn(screen, pygame.Rect(WIDTH - 120, 20, 100, 40), RED, "Back", font_med, WHITE)
        draw_btn(screen, pygame.Rect(WIDTH//2 - 150, 20, 140, 40), GREEN, "Play Test", font_med, BLACK)
        draw_btn(screen, pygame.Rect(WIDTH//2 + 10, 20, 140, 40), PURPLE, "Upload Map", font_med, WHITE)
        draw_btn(screen, pygame.Rect(WIDTH//2 - 310, 20, 140, 40), CYAN, "Randomize", font_med, BLACK)
        draw_btn(screen, pygame.Rect(WIDTH//2 + 170, 20, 150, 40), ORANGE if editor_is_unfair else DARK_GRAY, "Unfair Map", font_med, BLACK)
        draw_btn(screen, pygame.Rect(WIDTH - 250, 20, 110, 40), LIGHT_BLUE if editor_snap else GRAY, "Snap: ON" if editor_snap else "Snap: OFF", font_small, BLACK)
        
        screen.blit(font_med.render(f"Cloud Stats - Approved Maps: {len(approved_maps_list)} | Pending Queue: {len(pending_maps_list)}", True, CYAN), (20, HEIGHT - 70))

        for i, (t_name, t_color) in enumerate([('green', GREEN), ('gold', GOLD), ('bomb', DARK_GRAY), ('rainbow', WHITE), ('stat', CYAN), ('boss', MAGENTA), ('random', GRAY), ('bumper', GRAY)]):
            rect = pygame.Rect(20, 100 + i*50, 40, 40); pygame.draw.rect(screen, t_color, rect, border_radius=5)
            if editor_tool == t_name: pygame.draw.rect(screen, WHITE, rect, 3, border_radius=5)
            if t_name == 'random': screen.blit(font_med.render("?", True, BLACK), (rect.x+12, rect.y+10))
            if t_name == 'bumper': pygame.draw.circle(screen, WHITE, (rect.x+20, rect.y+20), 15, 2)
        
        l_clk, _, r_clk = pygame.mouse.get_pressed()
        if not is_uploading and 80 < my < max_y and 80 < mx < WIDTH - 130: 
            px, py = (round(mx/25)*25, round(my/25)*25) if editor_snap else (mx, my)
            if py > max_y: py = max_y 
            if l_clk:
                if editor_tool == 'bumper' and not any(math.hypot(b['x']-px, b['y']-py) < 25 for b in editor_bumpers):
                    editor_bumpers.append({'x': px, 'y': py, 'radius': 25})
                elif editor_tool != 'bumper' and not any(math.hypot(p['x']-px, p['y']-py) < 15 for p in editor_pegs):
                    editor_pegs.append({'x': float(px), 'y': float(py), 'type': editor_tool, 'active': True, 'on_fire': False, 'fire_timer': 0, 'is_random': editor_tool == 'random', **({'hp':5} if editor_tool=='boss' else {})})
            elif r_clk:
                editor_pegs = [p for p in editor_pegs if math.hypot(p['x']-mx, p['y']-my) > 15]; editor_bumpers = [b for b in editor_bumpers if math.hypot(b['x']-mx, b['y']-my) > b['radius']]
            
            pygame.draw.circle(screen, WHITE, (int(px), int(py)), 10, 1) 
            
        for b in editor_bumpers: pygame.draw.polygon(screen, GRAY, [(b['x'], b['y'] - b['radius']), (b['x'] + b['radius'], b['y']), (b['x'], b['y'] + b['radius']), (b['x'] - b['radius'], b['y'])]); pygame.draw.polygon(screen, WHITE, [(b['x'], b['y'] - b['radius']), (b['x'] + b['radius'], b['y']), (b['x'], b['y'] + b['radius']), (b['x'] - b['radius'], b['y'])], 2)
        for p in editor_pegs: draw_peg_visual(screen, p['x'], p['y'], p['type'])
        screen.blit(font_small.render("Hold L-Click: Draw | Hold R-Click: Erase", True, WHITE), (10, HEIGHT - 30))

        if is_uploading or upload_message:
            screen.blit(dim_overlay, (0,0)); u_rect = pygame.Rect(WIDTH//2 - 200, HEIGHT//2 - 50, 400, 100)
            pygame.draw.rect(screen, BLACK, u_rect, border_radius=10); pygame.draw.rect(screen, PURPLE, u_rect, 3, border_radius=10)
            msg = upload_message if upload_message else "Uploading to Server..."
            ms_surf = font_med.render(msg, True, WHITE); screen.blit(ms_surf, (u_rect.centerx - ms_surf.get_width()//2, u_rect.centery - ms_surf.get_height()//2))

    elif state == "PLAY":
        screen.fill(BLACK)
        if board_clear_timer == 0:
            for b_name, b_stat in ball_stats.items():
                if b_stat['unlocked'] and b_stat['auto_drop_lvl'] > 0 and b_stat.get('auto_enabled', True):
                    b_stat['auto_timer'] += 1
                    if b_stat['auto_timer'] >= get_auto_drop_rate(b_stat['auto_drop_lvl']) * FPS:
                        b_stat['auto_timer'] = 0; spawn_ball(b_name, random.choice(active_pegs)['x'] + random.uniform(-15, 15) if active_pegs and random.random() < 0.8 else random.randint(20, WIDTH-20), 20.0, random.uniform(-1, 1), 0.0)
        
        # --- NEW ACTIVE ABILITIES EFFECTS ---
        if fire_cursor_timer > 0:
            fire_cursor_timer -= 1
            pygame.draw.circle(screen, ORANGE, (mx, my), 75, 2)
            for p in pegs:
                if p['active'] and math.hypot(p['x']-mx, p['y']-my) < 75 and not p.get('on_fire'):
                    p['on_fire'] = True; p['fire_timer'] = FPS * 2

        if vacuum_cursor_timer > 0:
            vacuum_cursor_timer -= 1
            pygame.draw.circle(screen, LIGHT_BLUE, (mx, my), 200, 2)
            for b in balls:
                dx, dy = mx - b['x'], my - b['y']
                dist = max(1, math.hypot(dx, dy))
                if dist < 200:
                    b['vx'] += (dx/dist) * 1.5; b['vy'] += (dy/dist) * 1.5 - b['grav']

        for d in drones[:]:
            d['timer'] -= 1
            pygame.draw.rect(screen, WHITE, (int(d['x'])-20, int(d['y'])-10, 40, 20))
            pygame.draw.circle(screen, RED, (int(d['x']), int(d['y'])+10), 5)
            if d['timer'] <= 0:
                spawn_ball(equipped_ball, d['x'], d['y']+15, random.uniform(-2, 2), 0)
                d['balls_left'] -= 1; d['timer'] = FPS // 2
                if d['balls_left'] <= 0: drones.remove(d)

        for bh in black_holes[:]:
            bh['life'] -= 1
            pygame.draw.circle(screen, PURPLE, (int(bh['x']), int(bh['y'])), 30)
            pygame.draw.circle(screen, BLACK, (int(bh['x']), int(bh['y'])), 25)
            for p in pegs:
                if p['active']:
                    dx, dy = bh['x'] - p['x'], bh['y'] - p['y']
                    dist = math.hypot(dx, dy)
                    if dist < bh['radius']:
                        p['x'] += (dx/dist) * 3; p['y'] += (dy/dist) * 3
                        if dist < 30:
                            p['active'] = False; grant_peg_reward(p, 2.0, False, 'Regular')
            if bh['life'] <= 0: black_holes.remove(bh)

        for lz in lasers[:]:
            lz['life'] -= 1
            alpha = max(0, int((lz['life'] / FPS) * 255))
            surf = pygame.Surface((120, HEIGHT), pygame.SRCALPHA)
            surf.fill((255, 0, 0, alpha))
            screen.blit(surf, (int(lz['x']) - 60, 0))
            if lz['life'] <= 0: lasers.remove(lz)
                        
        for b in balls[:]:
            b['vy'] += b['grav']; b['x'] += b['vx']; b['y'] += b['vy']
            speed = math.hypot(b['vx'], b['vy'])
            if speed > 18.0: b['vx'] = (b['vx'] / speed) * 18.0; b['vy'] = (b['vy'] / speed) * 18.0
            rad = b.get('radius', BALL_RADIUS)
            
            if b['x'] - rad < 0 or b['x'] + rad > WIDTH:
                b['x'] = rad if b['x'] - rad < 0 else WIDTH - rad; b['vx'] *= -b['bounce']; bounce_sound.play()
                if b['type'] == 'Regular': cash += int(5 * (0.01 if is_playtest else 1))
            if b['y'] - rad > HEIGHT: balls.remove(b); continue 
            
            for bmp in bumpers:
                dx, dy = b['x'] - bmp['x'], b['y'] - bmp['y']; dist = math.hypot(dx, dy)
                if dist < rad + bmp['radius']:
                    bounce_sound.play(); nx, ny = dx / max(dist,0.1), dy / max(dist,0.1)
                    b['x'] += nx * ((rad + bmp['radius']) - dist); b['y'] += ny * ((rad + bmp['radius']) - dist)
                    dot = b['vx'] * nx + b['vy'] * ny; b['vx'] = (b['vx'] - 2 * dot * nx) * b['bounce']; b['vy'] = (b['vy'] - 2 * dot * ny) * b['bounce']

            for peg in pegs:
                if peg['active'] and math.hypot(b['x'] - peg['x'], b['y'] - peg['y']) < rad + (PEG_RADIUS * 1.5 if peg['type'] == 'boss' else PEG_RADIUS):
                    if b['type'] == 'Taco':
                        bite_sound.play(); b['hits_taken'] += 1
                        if peg['type'] == 'boss':
                            peg['hp'] = peg.get('hp', 5) - 1
                            if peg['hp'] <= 0: peg['active'] = False; grant_peg_reward(peg, b['gold_mult'], True, b['type'])
                        else: peg['active'] = False; grant_peg_reward(peg, b['gold_mult'], True, b['type'])
                        
                        nearby = sorted([p for p in pegs if p['active']], key=lambda p: math.hypot(peg['x']-p['x'], peg['y']-p['y']))[:2]
                        for np in nearby:
                            if math.hypot(peg['x']-np['x'], peg['y']-np['y']) < 80:
                                if np['type'] == 'boss':
                                    np['hp'] = np.get('hp', 5) - 1
                                    if np['hp'] <= 0: np['active'] = False; grant_peg_reward(np, b['gold_mult'], False, b['type'])
                                else: np['active'] = False; grant_peg_reward(np, b['gold_mult'], False, b['type'])
                                
                        if b['hits_taken'] >= b.get('max_hits', 3): balls.remove(b); break
                    else:
                        if peg['type'] == 'boss':
                            peg['hp'] = peg.get('hp', 5) - 1
                            if peg['hp'] <= 0: peg['active'] = False; grant_peg_reward(peg, b['gold_mult'], True, b['type'])
                        else: peg['active'] = False; grant_peg_reward(peg, b['gold_mult'], True, b['type'])
                        
                        if b['type'] == 'Bomb':
                            for _ in range(8): spawn_ball('Shrapnel', peg['x'], peg['y'], random.uniform(-10, 10), random.uniform(-10, -2))
                            balls.remove(b); break
                        elif b['type'] == 'Fire':
                            nearby = sorted([p for p in pegs if p['active'] and p != peg], key=lambda p: math.hypot(peg['x']-p['x'], peg['y']-p['y']))[:2]
                            for np in nearby:
                                if math.hypot(peg['x']-np['x'], peg['y']-np['y']) < 60 and not np.get('on_fire'): np['on_fire'] = True; np['fire_timer'] = FPS * 2
                                
                    bounce_sound.play(); nx, ny = (b['x'] - peg['x']) / max(math.hypot(b['x'] - peg['x'], b['y'] - peg['y']),0.1), (b['y'] - peg['y']) / max(math.hypot(b['x'] - peg['x'], b['y'] - peg['y']),0.1)
                    b['x'] += nx * ((rad + (PEG_RADIUS * 1.5 if peg['type'] == 'boss' else PEG_RADIUS)) - math.hypot(b['x'] - peg['x'], b['y'] - peg['y'])); b['y'] += ny * ((rad + (PEG_RADIUS * 1.5 if peg['type'] == 'boss' else PEG_RADIUS)) - math.hypot(b['x'] - peg['x'], b['y'] - peg['y']))
                    dot = b['vx'] * nx + b['vy'] * ny; b['vx'] = (b['vx'] - 2 * dot * nx) * b['bounce']; b['vy'] = (b['vy'] - 2 * dot * ny) * b['bounce']
                    break 

        for p in particles[:]:
            p['x'] += p['vx']; p['y'] += p['vy']; p['life'] -= 1; p['radius'] = max(0, p['radius'] - 0.1)
            if p['life'] <= 0: particles.remove(p)

        if all(not p['active'] for p in pegs) and len(pegs) > 0 and board_clear_timer == 0:
            board_clear_timer = FPS * 2; cash += int(100 * (0.01 if is_playtest else 1)); boards_cleared += 1
            for _ in range(10): spawn_particles(random.randint(200, WIDTH-200), random.randint(200, HEIGHT-200), random.choice([GOLD, CYAN, RED, GREEN]), count=30, speed=8.0)
        
        for bmp in bumpers: pygame.draw.polygon(screen, GRAY, [(bmp['x'], bmp['y'] - bmp['radius']), (bmp['x'] + bmp['radius'], bmp['y']), (bmp['x'], bmp['y'] + bmp['radius']), (bmp['x'] - bmp['radius'], bmp['y'])]); pygame.draw.polygon(screen, WHITE, [(bmp['x'], bmp['y'] - bmp['radius']), (bmp['x'] + bmp['radius'], bmp['y']), (bmp['x'], bmp['y'] + bmp['radius']), (bmp['x'] - bmp['radius'], bmp['y'])], 2)
        for peg in pegs:
            if peg['active']: 
                if peg.get('on_fire'):
                    peg['fire_timer'] -= 1
                    if random.random() < 0.1: spawn_particles(peg['x'], peg['y'], ORANGE, count=1, speed=1.0)
                    if peg['fire_timer'] <= 0:
                        if peg['type'] == 'boss':
                            peg['hp'] = peg.get('hp', 5) - 1
                            if peg['hp'] <= 0: peg['active'] = False; grant_peg_reward(peg, 1.0, False, 'Fire')
                            else: peg['on_fire'] = False
                        else: peg['active'] = False; grant_peg_reward(peg, 1.0, False, 'Fire')
                draw_peg_visual(screen, peg['x'], peg['y'], peg['type'], peg.get('hp', 0), peg.get('on_fire', False))
        for p in particles: pygame.draw.circle(screen, p['color'], (int(p['x']), int(p['y'])), int(p['radius']))
        
        for b in balls: 
            if b['type'] == 'Taco':
                b_rad = b.get('radius', 14); bx, by = int(b['x']), int(b['y'])
                pygame.draw.circle(screen, GOLD, (bx, by), b_rad); pygame.draw.rect(screen, BROWN, (bx - b_rad + 2, by - 2, b_rad * 2 - 4, 6)); pygame.draw.rect(screen, GREEN, (bx - b_rad + 4, by - 6, b_rad * 2 - 8, 4))
                health = 1.0 - (b.get('hits_taken', 0) / b.get('max_hits', 3))
                if health <= 0.75: pygame.draw.circle(screen, BLACK, (bx + b_rad, by - 5), 8)
                if health <= 0.50: pygame.draw.circle(screen, BLACK, (bx - b_rad, by + 5), 8)
                if health <= 0.25: pygame.draw.circle(screen, BLACK, (bx, by - b_rad), 8)
            else:
                pygame.draw.circle(screen, b['color'], (int(b['x']), int(b['y'])), b.get('radius', BALL_RADIUS)); pygame.draw.circle(screen, WHITE, (int(b['x'] - b.get('radius', BALL_RADIUS)*0.3), int(b['y'] - b.get('radius', BALL_RADIUS)*0.3)), max(1, int(b.get('radius', BALL_RADIUS)*0.2)))

        if is_playtest:
            draw_btn(screen, pygame.Rect(WIDTH//2 - 100, 20, 200, 50), RED, "END PLAYTEST", font_med, WHITE); screen.blit(font_small.render("(Earns 1% Cash)", True, GRAY), (WIDTH//2 - 60, 75))
        else:
            draw_btn(screen, pygame.Rect(WIDTH - 120, 20, 100, 40), TAN, "MENU", font_med, BLACK)
            auto_y = 70
            for b_name, b_stat in ball_stats.items():
                if b_stat['auto_drop_lvl'] > 0:
                    is_on = b_stat.get('auto_enabled', True); draw_btn(screen, pygame.Rect(WIDTH - 150, auto_y, 130, 35), GREEN if is_on else RED, f"{b_name[:6].upper()}: {'ON' if is_on else 'OFF'}", font_small, BLACK); auto_y += 45
            if not active_ability_mode: draw_cannon(mx, my)

        screen.blit(font_large.render(f"Cash: ${cash}", True, WHITE), (20, 10)); screen.blit(font_med.render(f"PP: {prestige_points}", True, BRONZE), (20, 45)); screen.blit(font_med.render(f"SP: {stat_points}", True, CYAN), (20, 75))
        screen.blit(font_med.render(f"{equipped_ball} Ammo: {max(0, ball_stats[equipped_ball]['max_balls'] - len([b for b in balls if b['is_manual'] and b['type'] == equipped_ball]))} / {ball_stats[equipped_ball]['max_balls']}", True, WHITE), (20, 105))
        
        if equipped_abilities:
            for i, a_name in enumerate(equipped_abilities):
                a_data = ABILITIES[a_name]
                rect = pygame.Rect(20, HEIGHT - 70 - (i * 60), 290, 50)
                draw_btn(screen, rect, GREEN if active_ability_mode == a_name else (DARK_GRAY if ability_inventory.get(a_name, 0) <= 0 else a_data['color']), f"{a_name} ({ability_inventory.get(a_name, 0)})", font_med, BLACK)

        if board_clear_timer > 0:
            board_clear_timer -= 1; clear_txt = font_huge.render("BOARD CLEARED!", True, CYAN); screen.blit(clear_txt, (WIDTH//2 - clear_txt.get_width()//2, HEIGHT//2 - clear_txt.get_height()//2))
            if board_clear_timer == 0:
                if is_playtest: pegs = copy.deepcopy(backup_pegs); bumpers = copy.deepcopy(backup_bumpers)
                else: create_random_board()
                balls.clear(); particles.clear()

    elif state == "MENU":
        if gift_popup_msg:
            screen.blit(dim_overlay, (0, 0))
            pop_rect = pygame.Rect(WIDTH//2 - 200, HEIGHT//2 - 100, 400, 200)
            pygame.draw.rect(screen, BLACK, pop_rect, border_radius=10)
            pygame.draw.rect(screen, GOLD, pop_rect, 4, border_radius=10)
            screen.blit(font_large.render("GIFT RECEIVED!", True, CYAN), (WIDTH//2 - 130, HEIGHT//2 - 60))
            screen.blit(font_med.render(gift_popup_msg, True, WHITE), (WIDTH//2 - 160, HEIGHT//2))
            draw_btn(screen, pygame.Rect(WIDTH//2 - 75, HEIGHT//2 + 50, 150, 40), GREEN, "AWESOME", font_med, BLACK)

    elif state == "ABILITIES_MENU":
        screen.fill(BLACK); menu_w, menu_h = 900, 700; m_x, m_y = WIDTH//2 - menu_w//2, HEIGHT//2 - menu_h//2
        pygame.draw.rect(screen, DARK_GRAY, (m_x, m_y, menu_w, menu_h), border_radius=10); pygame.draw.rect(screen, LIGHT_BLUE, (m_x, m_y, menu_w, menu_h), 3, border_radius=10)
        screen.blit(font_large.render("--- ACTIVE ABILITIES ---", True, LIGHT_BLUE), (m_x + menu_w//2 - 200, m_y + 20)); screen.blit(font_med.render(f"Equipped: {len(equipped_abilities)} / 5", True, WHITE), (m_x + menu_w//2 - 90, m_y + 60))
        for i, (a_name, a_data) in enumerate(ABILITIES.items()):
            card = pygame.Rect(m_x + 30 + ((i % 2) * 430), m_y + 100 + ((i // 2) * 90), 410, 80)
            pygame.draw.rect(screen, BLACK, card, border_radius=5); pygame.draw.rect(screen, RARITY_COLORS[a_data['rarity']], card, 2, border_radius=5)
            if a_name in equipped_abilities: pygame.draw.rect(screen, GREEN, card, 4, border_radius=5); screen.blit(font_med.render("EQ", True, GREEN), (card.x + card.width - 45, card.y + 25))
            screen.blit(font_med.render(a_name, True, a_data['color']), (card.x + 15, card.y + 10)); screen.blit(font_small.render(f"Tokens: {ability_inventory.get(a_name, 0)}", True, WHITE if ability_inventory.get(a_name, 0) > 0 else RED), (card.x + 15, card.y + 45))
            desc_w = a_data['desc'].split(); screen.blit(font_tiny.render(" ".join(desc_w[:5]), True, GRAY), (card.x + 175, card.y + 20)); screen.blit(font_tiny.render(" ".join(desc_w[5:]), True, GRAY), (card.x + 175, card.y + 40))
        draw_btn(screen, pygame.Rect(m_x + 30, m_y + menu_h - 60, 220, 40), GOLD, "Buy Crates", font_med, BLACK)
        draw_btn(screen, pygame.Rect(m_x + menu_w//2 - 100, m_y + menu_h - 60, 200, 40), RED, "Unequip All", font_med, WHITE)
        draw_btn(screen, pygame.Rect(m_x + menu_w - 130, m_y + 20, 100, 40), RED, "Back", font_med, WHITE)

    elif state == "CRATES_MENU":
        screen.fill(BLACK); menu_w, menu_h = 1000, 700; m_x, m_y = WIDTH//2 - menu_w//2, HEIGHT//2 - menu_h//2
        pygame.draw.rect(screen, DARK_BLUE, (m_x, m_y, menu_w, menu_h), border_radius=10); pygame.draw.rect(screen, GOLD, (m_x, m_y, menu_w, menu_h), 3, border_radius=10)
        screen.blit(font_huge.render("ABILITY CRATES", True, GOLD), (m_x + menu_w//2 - 250, m_y + 30)); screen.blit(font_med.render(f"Current Cash: ${cash}", True, WHITE), (m_x + menu_w//2 - 120, m_y + 100))
        for i, (c_name, c_data) in enumerate(CRATES.items()):
            card = pygame.Rect(m_x + 73 + i*293, m_y + 170, 260, 350); pygame.draw.rect(screen, BLACK, card, border_radius=10); pygame.draw.rect(screen, c_data['color'], card, 4, border_radius=10)
            screen.blit(font_large.render(c_name.split()[0], True, c_data['color']), (card.x + 50, card.y + 20)); screen.blit(font_large.render(c_name.split()[1], True, c_data['color']), (card.x + 70, card.y + 60))
            screen.blit(font_med.render(f"Cost: ${c_data['cost']}", True, GOLD), (card.x + 40, card.y + 120)); screen.blit(font_med.render(f"Rolls: {c_data['rolls']}", True, WHITE), (card.x + 85, card.y + 160))
            y_off = 240
            for rarity in ['Common', 'Rare', 'Epic', 'Legendary']: screen.blit(font_small.render(f"{rarity}: {int(c_data['odds'][rarity]*100)}%", True, RARITY_COLORS[rarity]), (card.x + 20, card.y + y_off)); y_off += 25
            draw_btn(screen, pygame.Rect(card.x + 30, card.y + 360, 200, 40), GREEN if cash >= c_data['cost'] else GRAY, "BUY CRATE", font_med, BLACK)
        draw_btn(screen, pygame.Rect(m_x + menu_w//2 - 75, m_y + menu_h - 70, 150, 40), RED, "Back", font_med, WHITE)

    elif state == "CONFIRM_DELETE":
        screen.blit(dim_overlay, (0, 0))
        pygame.draw.rect(screen, BLACK, (WIDTH//2 - 300, HEIGHT//2 - 150, 600, 300), border_radius=10)
        pygame.draw.rect(screen, RED, (WIDTH//2 - 300, HEIGHT//2 - 150, 600, 300), 4, border_radius=10)
        screen.blit(font_large.render("WARNING: DELETE ALL DATA?", True, RED), (WIDTH//2 - 250, HEIGHT//2 - 100))
        screen.blit(font_med.render("This will erase EVERYTHING. Cannot be undone.", True, WHITE), (WIDTH//2 - 270, HEIGHT//2 - 30))
        draw_btn(screen, pygame.Rect(WIDTH//2 - 150, HEIGHT//2 + 50, 100, 50), RED, "NUKE IT", font_med, WHITE)
        draw_btn(screen, pygame.Rect(WIDTH//2 + 50, HEIGHT//2 + 50, 100, 50), GREEN, "CANCEL", font_med, BLACK)

    elif state == "PRESTIGE_TREE":
        screen.fill(DARK_BG)
        for node in tree_nodes: pygame.draw.line(screen, GREEN if p_upgrades.get(node['key'], 0) >= node['level'] else RED, (node['prev_x'], node['prev_y']), (node['x'], node['y']), 3)
        pygame.draw.circle(screen, GOLD, (int(tree_center[0]), int(tree_center[1])), 25); pygame.draw.circle(screen, WHITE, (int(tree_center[0]), int(tree_center[1])), 25, 3)
        c_txt = font_tiny.render("CORE", True, BLACK); screen.blit(c_txt, (tree_center[0] - c_txt.get_width()//2, tree_center[1] - c_txt.get_height()//2))

        for node in tree_nodes:
            lvl = p_upgrades.get(node['key'], 0); fill, border = (node['color'], GREEN) if lvl >= node['level'] else ((BLACK, GOLD) if lvl == node['level'] - 1 else (BLACK, DARK_GRAY))
            pygame.draw.circle(screen, fill, (int(node['x']), int(node['y'])), 16); pygame.draw.circle(screen, border, (int(node['x']), int(node['y'])), 16, 3)
            if math.hypot(mx - node['x'], my - node['y']) <= 16:
                pygame.draw.circle(screen, WHITE, (int(node['x']), int(node['y'])), 16, 4)
                d = PRESTIGE_DEFS[node['key']]; clvl = p_upgrades.get(node['key'], 0)
                stat_str = "(Purchased)" if clvl >= node['level'] else (f"(Cost: {node['cost']} PP)" if clvl == node['level'] - 1 else "(Locked)")
                tt_x, tt_y = mx + 15, my + 15
                if tt_x + 240 > WIDTH: tt_x = mx - 240 - 15 
                if tt_y + 90 > HEIGHT: tt_y = my - 90 - 15
                pygame.draw.rect(screen, TAN, (tt_x, tt_y, 240, 90), border_radius=5); pygame.draw.rect(screen, BLACK, (tt_x, tt_y, 240, 90), 2, border_radius=5)
                screen.blit(font_small.render(f"{d['name']} Lvl {node['level']}", True, BLACK), (tt_x + 10, tt_y + 10))
                screen.blit(font_small.render(stat_str, True, DARK_GRAY), (tt_x + 10, tt_y + 35)); screen.blit(font_small.render(d['desc'], True, BLACK), (tt_x + 10, tt_y + 60))

        screen.blit(font_large.render(f"{prestige_points} PP", True, BRONZE), (75, 25))
        draw_btn(screen, pygame.Rect(WIDTH - 120, 20, 100, 40), RED, "CLOSE", font_med, WHITE)

    elif state == "CRATE_REWARD":
        screen.fill(BLACK); screen.blit(font_huge.render("CRATE OPENED!", True, GOLD), (WIDTH//2 - 220, 100)); cols = 5; rows = math.ceil(len(crate_results_display) / cols); start_y = HEIGHT // 2 - (rows * 60)
        for i, res in enumerate(crate_results_display):
            r = i // cols; c = i % cols; x = WIDTH//2 - (cols * 100) + (c * 200) + 100; y = start_y + (r * 150); r_col = RARITY_COLORS[res['rarity']]
            pygame.draw.rect(screen, DARK_GRAY, (x - 80, y, 160, 100), border_radius=10); pygame.draw.rect(screen, r_col, (x - 80, y, 160, 100), 3, border_radius=10)
            screen.blit(font_med.render(res['rarity'], True, r_col), (x - 60, y + 10))
            wds = res['name'].split()
            if len(wds) > 1: screen.blit(font_small.render(wds[0], True, WHITE), (x - 60, y + 45)); screen.blit(font_small.render(wds[1], True, WHITE), (x - 60, y + 70))
            else: screen.blit(font_small.render(res['name'], True, WHITE), (x - 60, y + 55))
        draw_btn(screen, pygame.Rect(WIDTH//2 - 75, HEIGHT - 150, 150, 50), GREEN, "AWESOME", font_med, BLACK)
        
    elif state == "OFFLINE_SCREEN":
        screen.fill(DARK_BG)
        anim_cash += (offline_rewards['cash'] - anim_cash) * 0.05 + 1; anim_pp += (offline_rewards['pp'] - anim_pp) * 0.05 + 0.1; anim_sp += (offline_rewards['sp'] - anim_sp) * 0.05 + 0.1
        if anim_cash > offline_rewards['cash']: anim_cash = offline_rewards['cash']
        if anim_pp > offline_rewards['pp']: anim_pp = offline_rewards['pp']
        if anim_sp > offline_rewards['sp']: anim_sp = offline_rewards['sp']
        pygame.draw.rect(screen, BLACK, (WIDTH//2 - 300, HEIGHT//2 - 250, 600, 500), border_radius=15); pygame.draw.rect(screen, CYAN, (WIDTH//2 - 300, HEIGHT//2 - 250, 600, 500), 4, border_radius=15)
        screen.blit(font_huge.render("WELCOME BACK!", True, GOLD), (WIDTH//2 - 260, HEIGHT//2 - 220)); screen.blit(font_med.render(f"You were gone for {format_time(offline_rewards['time'])}", True, GRAY), (WIDTH//2 - 180, HEIGHT//2 - 140))
        screen.blit(font_large.render(f"Cash Earned: ${int(anim_cash)}", True, GREEN), (WIDTH//2 - 200, HEIGHT//2 - 60)); screen.blit(font_large.render(f"PP Earned: {int(anim_pp)}", True, BRONZE), (WIDTH//2 - 200, HEIGHT//2 - 10)); screen.blit(font_large.render(f"SP Earned: {int(anim_sp)}", True, CYAN), (WIDTH//2 - 200, HEIGHT//2 + 40))
        draw_btn(screen, pygame.Rect(WIDTH//2 - 100, HEIGHT - 150, 200, 60), GREEN if int(anim_cash) == offline_rewards['cash'] and int(anim_pp) == offline_rewards['pp'] and int(anim_sp) == offline_rewards['sp'] else GRAY, "COLLECT", font_large, BLACK)
        
    elif state == "CONFIRM_PRESTIGE":
        screen.blit(dim_overlay, (0, 0)); pygame.draw.rect(screen, TAN, (WIDTH//2 - 250, HEIGHT//2 - 100, 500, 200), border_radius=10); pygame.draw.rect(screen, GOLD, (WIDTH//2 - 250, HEIGHT//2 - 100, 500, 200), 3, border_radius=10)
        screen.blit(font_med.render("Are you sure you want to Prestige?", True, BLACK), (WIDTH//2 - 210, HEIGHT//2 - 80)); screen.blit(font_small.render("You will lose cash and ball upgrades, but keep PP and get SP refunded.", True, DARK_GRAY), (WIDTH//2 - 240, HEIGHT//2 - 30))
        draw_btn(screen, pygame.Rect(WIDTH//2 - 150, HEIGHT//2 + 20, 100, 50), GREEN, "YES", font_med, BLACK); draw_btn(screen, pygame.Rect(WIDTH//2 + 50, HEIGHT//2 + 20, 100, 50), RED, "NO", font_med, WHITE)

    pygame.display.flip(); clock.tick(FPS)
