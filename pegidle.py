import pygame
import math
import random
import os
import wave
import struct
import json
import time

# --- Configuration ---
WIDTH, HEIGHT = 1200, 800 
FPS = 60
SAVE_FILE = "peggle_save_v18.json" 

# Colors
GREEN = (50, 200, 50)
GOLD = (255, 215, 0)
WHITE = (255, 255, 255)
BLACK = (20, 20, 30)
DARK_BG = (25, 30, 40) 
RED = (255, 50, 50)
GRAY = (150, 150, 150)
DARK_GRAY = (60, 60, 60)
BROWN = (139, 69, 19)      
BRONZE = (205, 127, 50)    
TAN = (210, 180, 140)
CYAN = (50, 255, 255)
LIGHT_BLUE = (100, 200, 255)
ORANGE = (255, 140, 0)
PURPLE = (150, 50, 200)
MAROON = (128, 0, 0)
DARK_BLUE = (30, 40, 80)
MAGENTA = (255, 0, 255) 

# --- Initialize Pygame & Mixer ---
pygame.init()
pygame.mixer.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Peggle Idle/Upgrades")
clock = pygame.time.Clock()

dim_overlay = pygame.Surface((WIDTH, HEIGHT))
dim_overlay.set_alpha(200)
dim_overlay.fill(BLACK)

fx_surface = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)

font_huge = pygame.font.SysFont(None, 80)
font_large = pygame.font.SysFont(None, 48)
font_med = pygame.font.SysFont(None, 36)
font_small = pygame.font.SysFont(None, 24)
font_tiny = pygame.font.SysFont(None, 18)

# --- Auto-Generate Bounce Sound ---
def create_bounce_sound(filename="bounce.wav"):
    if not os.path.exists(filename):
        sample_rate, duration, frequency = 44100, 0.05, 600.0
        wavef = wave.open(filename, 'w')
        wavef.setnchannels(1) 
        wavef.setsampwidth(2) 
        wavef.setframerate(sample_rate)
        for i in range(int(sample_rate * duration)):
            value = int(32767.0 * math.sin(frequency * math.pi * 2.0 * i / sample_rate))
            envelope = 1.0 - (i / (sample_rate * duration))
            data = struct.pack('<h', int(value * envelope))
            wavef.writeframesraw(data)
        wavef.close()

create_bounce_sound()
bounce_sound = pygame.mixer.Sound("bounce.wav")
bounce_sound.set_volume(0.2) 

# --- Ball & Ability Databases ---
BALL_TYPES = {
    "Regular": {"color": RED, "base_grav": 0.25, "base_bounce": 0.85, "cost": 0, "desc": "Gains $5 on wall bounce"},
    "Fire":    {"color": ORANGE, "base_grav": 0.25, "base_bounce": 0.70, "cost": 2500, "desc": "Sets pegs on fire!"},
    "Boulder": {"color": DARK_GRAY, "base_grav": 0.45, "base_bounce": 0.50, "cost": 1500, "desc": "Smashes 3 pegs on ground hit"},
    "Bomb":    {"color": DARK_BLUE, "base_grav": 0.30, "base_bounce": 0.60, "cost": 5000, "desc": "Explodes into shrapnel"},
    "Bouncy":  {"color": CYAN, "base_grav": 0.15, "base_bounce": 0.95, "cost": 15000, "desc": "Multiplier grows on wall hits"},
    "Maroon":  {"color": MAROON, "base_grav": 0.35, "base_bounce": 0.70, "cost": 50000, "desc": "Bounces off the bottom once"},
    "Hoops":   {"color": ORANGE, "base_grav": 0.25, "base_bounce": 0.92, "cost": 150000, "desc": "Teleports to top on drop"},
    "Magic":   {"color": PURPLE, "base_grav": 0.0, "base_bounce": 0.90, "cost": 500000, "desc": "Floats & Zaps"},
    "Wood":    {"color": BROWN, "base_grav": 0.30, "base_bounce": 0.65, "cost": 1000000, "desc": "Passively grows money mid-air"},
    "Shrapnel": {"color": GRAY, "base_grav": 0.30, "base_bounce": 0.60, "cost": 0, "desc": "", "hidden": True} 
}

# --- CRATES & TOKEN SYSTEM ---
RARITY_COLORS = {'Common': GRAY, 'Rare': LIGHT_BLUE, 'Epic': PURPLE, 'Legendary': GOLD}

ABILITIES = {
    "Fire Cursor": {"desc": "5s Buff: Hold click to burn pegs", "color": ORANGE, "rarity": "Common"},
    "Vacuum Cursor": {"desc": "5s Buff: Hold click to juggle balls!", "color": LIGHT_BLUE, "rarity": "Common"},
    "Thunder Cloud": {"desc": "Click to spawn a storm cloud!", "color": DARK_GRAY, "rarity": "Rare"},
    "Bounce Revive": {"desc": "Instantly gives active balls an extra bounce!", "color": GREEN, "rarity": "Rare"},
    "Midas Touch": {"desc": "Click to turn an area of pegs into Gold!", "color": GOLD, "rarity": "Epic"},
    "Starfall": {"desc": "Instantly drops 10 bouncy balls!", "color": LIGHT_BLUE, "rarity": "Epic"},
    "Drone": {"desc": "Collects 10 balls. Click to drop them!", "color": WHITE, "rarity": "Epic"},
    "Revive Wave": {"desc": "Teleports active balls back to the top!", "color": CYAN, "rarity": "Legendary"},
    "Black Hole": {"desc": "Sucks pegs for 6s. Pegs eaten pay 2x!", "color": PURPLE, "rarity": "Legendary"},
    "Orbital Strike": {"desc": "Blasts a vertical column with a laser!", "color": RED, "rarity": "Legendary"}
}

CRATES = {
    "Basic Crate": {"cost": 2000, "rolls": 3, "odds": {"Legendary": 0.02, "Epic": 0.08, "Rare": 0.30, "Common": 0.60}, "color": BROWN},
    "Advanced Crate": {"cost": 10000, "rolls": 6, "odds": {"Legendary": 0.08, "Epic": 0.20, "Rare": 0.42, "Common": 0.30}, "color": DARK_GRAY},
    "Premium Crate": {"cost": 40000, "rolls": 10, "odds": {"Legendary": 0.25, "Epic": 0.40, "Rare": 0.25, "Common": 0.10}, "color": GOLD}
}

PRESTIGE_DEFS = {
    'starter_cash': {'name': 'Starter Money', 'desc': '+$1000 on Prestige', 'base_cost': 5, 'max_lvl': 10},
    'extra_rainbow': {'name': 'More Rainbows', 'desc': '+1 Rainbow Peg', 'base_cost': 15, 'max_lvl': 5},
    'bomb_chance': {'name': 'Bomb Chance', 'desc': '+2% Bomb spawn rate', 'base_cost': 10, 'max_lvl': 10},
    'extra_prestige': {'name': 'Prestige Pegs', 'desc': '+1 Brown Peg', 'base_cost': 12, 'max_lvl': 5},
    'gold_chance': {'name': 'Gold Rush', 'desc': '+5% Gold Peg rate', 'base_cost': 10, 'max_lvl': 10},
    'multishot': {'name': 'Multishot', 'desc': '+1 Ball per manual shot', 'base_cost': 25, 'max_lvl': 5},
    'stat_pegs': {'name': 'Stat Pegs', 'desc': '+10% Stat Peg rate', 'base_cost': 15, 'max_lvl': 5} 
}

# --- Game State Variables ---
state = "PLAY"
view_only_tree = False 
cash = 0
prestige_points = 0
stat_points = 0 
equipped_ball = "Regular"
ability_inventory = {k: 0 for k in ABILITIES.keys()} 
equipped_abilities = [] 
active_ability_mode = None 

# Buff Timers
fire_ability_timer = 0
fire_cursor_timer = 0
vacuum_cursor_timer = 0

boards_cleared = 0
last_save_time = time.time()

# Offline Animation Tracking
offline_rewards = {}
anim_cash = 0.0
anim_pp = 0.0
anim_sp = 0.0
crate_results_display = []

p_upgrades = {k: 0 for k in PRESTIGE_DEFS.keys()}

balls = [] 
pegs = []
bumpers = [] 
particles = [] 
lightnings = [] 
clouds = [] 
black_holes = [] 
lasers = [] 
drones = []

CANNON_POS = (WIDTH // 2, 40)
PEG_RADIUS = 12
BALL_RADIUS = 10
board_clear_timer = 0
event_text_str = ""
event_timer = 0

def get_default_ball_stats(unlocked=False):
    return {
        'unlocked': unlocked, 'level': 1, 'gold_mult': 1.0, 'bounce_bonus': 0.0,
        'max_balls': 1, 'auto_drop_lvl': 0,
        'upg_cost_power': 50, 'upg_cost_balls': 100, 'upg_cost_auto': 250,
        'auto_timer': 0, 'auto_enabled': True,
        'special_unlocked': False,     
        'base_top_revives': 0,         
        'base_bounce_revives': 0       
    }

ball_stats = {name: get_default_ball_stats(unlocked=(name=="Regular")) for name in BALL_TYPES.keys()}

def save_game():
    data = {
        'cash': cash, 'prestige_points': prestige_points, 'stat_points': stat_points,
        'equipped_ball': equipped_ball, 'equipped_abilities': equipped_abilities, 
        'ability_inventory': ability_inventory,
        'boards_cleared': boards_cleared,
        'ball_stats': ball_stats, 'p_upgrades': p_upgrades,
        'last_save_time': time.time()
    }
    with open(SAVE_FILE, 'w') as f: json.dump(data, f)

def load_game():
    global cash, prestige_points, stat_points, equipped_ball, equipped_abilities, ability_inventory, boards_cleared, ball_stats, p_upgrades, last_save_time
    if os.path.exists(SAVE_FILE):
        try:
            with open(SAVE_FILE, 'r') as f:
                data = json.load(f)
                cash = data.get('cash', cash)
                prestige_points = data.get('prestige_points', prestige_points)
                stat_points = data.get('stat_points', stat_points)
                equipped_ball = data.get('equipped_ball', equipped_ball)
                
                loaded_inv = data.get('ability_inventory', {})
                for k in ability_inventory.keys(): ability_inventory[k] = loaded_inv.get(k, 0)
                
                equipped_abilities = data.get('equipped_abilities', equipped_abilities)
                boards_cleared = data.get('boards_cleared', boards_cleared)
                last_save_time = data.get('last_save_time', time.time())
                
                loaded_p = data.get('p_upgrades', {})
                for k in p_upgrades.keys(): p_upgrades[k] = loaded_p.get(k, 0)
                loaded_stats = data.get('ball_stats', {})
                for k, v in loaded_stats.items():
                    if k in ball_stats: 
                        ball_stats[k].update(v)
                        if 'special_unlocked' not in ball_stats[k]: ball_stats[k]['special_unlocked'] = False
                        if 'base_top_revives' not in ball_stats[k]: ball_stats[k]['base_top_revives'] = 0
                        if 'base_bounce_revives' not in ball_stats[k]: ball_stats[k]['base_bounce_revives'] = 0
        except: pass

load_game()


def trigger_event(text):
    global event_text_str, event_timer
    event_text_str = text
    event_timer = FPS * 2 

def populate_pegs(coords_list):
    global pegs
    pegs = []
    bomb_rate = 0.05 + (p_upgrades.get('bomb_chance', 0) * 0.02)
    gold_rate = 0.25 + (p_upgrades.get('gold_chance', 0) * 0.05)
    
    for x, y in coords_list:
        rand_val = random.random()
        if rand_val < bomb_rate: peg_type = 'bomb'
        elif rand_val < bomb_rate + gold_rate: peg_type = 'gold'
        else: peg_type = 'green'
        
        pegs.append({'x': float(x), 'y': float(y), 'type': peg_type, 'active': True, 'on_fire': False, 'fire_timer': 0})

    indices = list(range(len(pegs)))
    random.shuffle(indices)

    stat_chance = 0.5 + (p_upgrades.get('stat_pegs', 0) * 0.10)
    num_stat_pegs = int(stat_chance)
    if random.random() < (stat_chance - num_stat_pegs):
        num_stat_pegs += 1
        
    for i in range(min(num_stat_pegs, len(indices))): 
        pegs[indices[i]]['type'] = 'stat'

    remaining_indices = indices[num_stat_pegs:]
    random.shuffle(remaining_indices)

    num_rainbow = random.randint(1, 3) + p_upgrades.get('extra_rainbow', 0)
    for i in range(min(num_rainbow, len(remaining_indices))): 
        pegs[remaining_indices[i]]['type'] = 'rainbow'
        
    remaining_indices = remaining_indices[num_rainbow:]
    random.shuffle(remaining_indices)

    num_prestige = 1 + p_upgrades.get('extra_prestige', 0)
    for i in range(min(num_prestige, len(remaining_indices))):
        pegs[remaining_indices[i]]['type'] = 'prestige'
        
    remaining_indices = remaining_indices[num_prestige:]
    random.shuffle(remaining_indices)
        
    boss_indices = remaining_indices[:min(3, len(remaining_indices))]
    for idx in boss_indices:
        pegs[idx]['type'] = 'boss'
        pegs[idx]['hp'] = 5 

def layout_classic():
    coords = []
    for row in range(14): 
        offset = 20 if row % 2 != 0 else 0
        for col in range(28): 
            x = (col * 40) + offset + 40
            if 24 < x < WIDTH - 24: coords.append((x, 150 + row * 35))
    return coords

def layout_pillars():
    coords = []
    global bumpers
    bumpers = []
    columns_x = [200, 400, 600, 800, 1000] 
    for cx in columns_x:
        for row in range(15):
            offset = 15 if row % 2 != 0 else -15
            coords.append((cx + offset, 150 + row * 32))
            coords.append((cx + offset + 35, 150 + row * 32))
            
    bumpers.append({'x': 300, 'y': 350, 'radius': 25})
    bumpers.append({'x': 500, 'y': 250, 'radius': 25})
    bumpers.append({'x': 700, 'y': 350, 'radius': 25})
    bumpers.append({'x': 900, 'y': 250, 'radius': 25})
    return coords

def layout_floating_islands():
    coords = []
    global bumpers
    bumpers = []
    islands = [(250, 200), (950, 250), (600, 400), (450, 600), (750, 600), (250, 550), (950, 550)]
    for ix, iy in islands:
        for row in range(3):
            for col in range(6): coords.append((ix - 75 + col*30, iy - 30 + row*30))
                
    bumpers.append({'x': 600, 'y': 250, 'radius': 25})
    bumpers.append({'x': 400, 'y': 400, 'radius': 25})
    bumpers.append({'x': 800, 'y': 400, 'radius': 25})
    return coords

def layout_clusters():
    coords = []
    global bumpers
    bumpers = []
    centers = [(300, 250), (600, 250), (900, 250), (450, 500), (750, 500)]
    for cx, cy in centers:
        offsets = [(0,0), (-30,0), (30,0), (0,-30), (0,30), (-15,-15), (15,-15), (-15,15), (15,15)]
        for ox, oy in offsets: coords.append((cx + ox, cy + oy))
            
    bumpers.append({'x': 450, 'y': 350, 'radius': 30})
    bumpers.append({'x': 750, 'y': 350, 'radius': 30})
    bumpers.append({'x': 600, 'y': 600, 'radius': 30})
    return coords

def layout_boxes():
    coords = []
    global bumpers
    bumpers = []
    box_centers = [
        (240, 250), (480, 250), (720, 250), (960, 250),
        (240, 450), (480, 450), (720, 450), (960, 450),
        (360, 650), (600, 650), (840, 650)
    ]
    for cx, cy in box_centers:
        for bx in [-35, 0, 35]:
            for by in [-35, 0, 35]:
                if bx == 0 and by == 0: continue 
                x, y = cx + bx, cy + by
                if 24 < x < WIDTH - 24 and y < HEIGHT - 50:
                    coords.append((x, y))
                    
    bumpers.append({'x': 120, 'y': 350, 'radius': 25})
    bumpers.append({'x': 1080, 'y': 350, 'radius': 25})
    bumpers.append({'x': 120, 'y': 650, 'radius': 25})
    bumpers.append({'x': 1080, 'y': 650, 'radius': 25})
    return coords

def create_random_board():
    global bumpers, lightnings, clouds, black_holes, lasers
    bumpers = [] 
    lightnings = []
    clouds = []
    black_holes = []
    lasers = []
    layouts = [layout_classic, layout_pillars, layout_floating_islands, layout_clusters, layout_boxes]
    chosen_layout = random.choice(layouts)
    coords = chosen_layout()
    populate_pegs(coords)

if not pegs:
    create_random_board()

def get_auto_drop_rate(lvl):
    rates = [0, 2.0, 1.0, 0.5, 0.2]
    return rates[lvl] if lvl < len(rates) else 0.2

# --- TRUE OFFLINE SIMULATOR LOGIC ---
def check_offline_progress():
    global state, offline_rewards, anim_cash, anim_pp, anim_sp, last_save_time, boards_cleared
    now = time.time()
    delta = now - last_save_time
    
    if delta > 60: 
        b_stat = ball_stats[equipped_ball]
        
        if b_stat['unlocked'] and b_stat['auto_drop_lvl'] > 0 and b_stat.get('auto_enabled', True):
            rate = get_auto_drop_rate(b_stat['auto_drop_lvl'])
            if rate > 0:
                total_drops = int(delta / rate)
                
                sim_cash = 0
                sim_pp = 0
                sim_sp = 0
                
                MAX_ITER = 5000
                multiplier = 1
                if total_drops > MAX_ITER:
                    multiplier = total_drops // MAX_ITER
                    total_drops = MAX_ITER
                    
                for _ in range(total_drops):
                    active_pegs = [p for p in pegs if p['active']]
                    
                    if not active_pegs:
                        boards_cleared += 1 * multiplier
                        sim_cash += 100
                        create_random_board()
                        active_pegs = [p for p in pegs if p['active']]
                        
                    hits = random.randint(1, min(6, len(active_pegs)))
                    hit_pegs = random.sample(active_pegs, hits)
                    
                    for peg in hit_pegs:
                        peg['active'] = False
                        if peg['type'] == 'prestige':
                            sim_pp += 3
                        elif peg['type'] == 'stat':
                            sim_sp += 1
                        elif peg['type'] == 'boss':
                            sim_cash += int(500 * b_stat['gold_mult'])
                        else:
                            base_val = 10 if peg['type'] == 'gold' else (5 if peg['type'] in ['bomb', 'rainbow'] else 0)
                            if base_val > 0: 
                                sim_cash += int(base_val * b_stat['gold_mult'])
                    
                    if equipped_ball == "Regular":
                        sim_cash += 5 * random.randint(1, 3)
                    elif equipped_ball == "Wood":
                        sim_cash += int(10 * b_stat['gold_mult']) * random.randint(1, 2)
                
                sim_cash *= multiplier
                sim_pp *= multiplier
                sim_sp *= multiplier

                if sim_cash > 0 or sim_pp > 0 or sim_sp > 0:
                    offline_rewards = {'cash': sim_cash, 'pp': sim_pp, 'sp': sim_sp, 'time': int(delta)}
                    anim_cash, anim_pp, anim_sp = 0.0, 0.0, 0.0
                    state = "OFFLINE_SCREEN"

check_offline_progress()

def format_time(seconds):
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    if h > 0: return f"{h}h {m}m"
    return f"{m}m {s}s"

def perform_prestige_reset():
    global cash, stat_points, ball_stats, equipped_ball, equipped_abilities, active_ability_mode, balls, boards_cleared, particles, lightnings, clouds, black_holes, lasers, drones
    cash = p_upgrades['starter_cash'] * 1000
    boards_cleared = 0
    equipped_ball = "Regular"
    equipped_abilities = [] 
    active_ability_mode = None
    balls = []
    particles = []
    lightnings = []
    clouds = []
    black_holes = []
    lasers = []
    drones = []
    
    for b_name, b_stat in ball_stats.items():
        top_lvl = b_stat.get('base_top_revives', 0)
        bot_lvl = b_stat.get('base_bounce_revives', 0)
        stat_points += (top_lvl * (top_lvl + 1)) // 2
        stat_points += (bot_lvl * (bot_lvl + 1)) // 2
        
    ball_stats = {name: get_default_ball_stats(unlocked=(name=="Regular")) for name in BALL_TYPES.keys()}
    create_random_board()
    save_game()

def get_rainbow_color():
    t = pygame.time.get_ticks() / 300.0
    r = int((math.sin(t) + 1) * 127.5)
    g = int((math.sin(t + 2) + 1) * 127.5)
    b = int((math.sin(t + 4) + 1) * 127.5)
    return (r, g, b)

def generate_tree_nodes():
    nodes = []
    center = (WIDTH//2, HEIGHT//2 + 30)
    
    angles = [i * (2 * math.pi / 7) - math.pi / 2 for i in range(7)]
    
    branches = [
        ('starter_cash', angles[0], GREEN),        
        ('extra_rainbow', angles[1], CYAN),        
        ('bomb_chance', angles[2], ORANGE),         
        ('extra_prestige', angles[3], BROWN),       
        ('gold_chance', angles[4], GOLD),         
        ('multishot', angles[5], PURPLE),
        ('stat_pegs', angles[6], WHITE) 
    ]
    for key, angle, color in branches:
        data = PRESTIGE_DEFS[key]
        prev_pos = center
        for lvl in range(1, data['max_lvl'] + 1):
            spacing = 40 if data['max_lvl'] <= 5 else 25 
            dist = 50 + (lvl - 1) * spacing 
            x = center[0] + math.cos(angle) * dist
            y = center[1] + math.sin(angle) * dist
            nodes.append({
                'key': key, 'level': lvl, 'x': x, 'y': y,
                'prev_x': prev_pos[0], 'prev_y': prev_pos[1],
                'color': color, 'cost': data['base_cost'] * lvl
            })
            prev_pos = (x, y)
    return center, nodes

tree_center, tree_nodes = generate_tree_nodes()

def spawn_particles(x, y, color, count=15, speed=4.0):
    for _ in range(count):
        particles.append({
            'x': x, 'y': y,
            'vx': random.uniform(-speed, speed), 'vy': random.uniform(-speed, speed),
            'life': random.uniform(20, 40), 'color': color, 'radius': random.uniform(2, 5)
        })

def draw_cannon(mouse_x, mouse_y):
    dx, dy = mouse_x - CANNON_POS[0], mouse_y - CANNON_POS[1]
    angle = math.atan2(dy, dx)
    pygame.draw.circle(screen, GRAY, CANNON_POS, 25)
    end_x = CANNON_POS[0] + math.cos(angle) * 50
    end_y = CANNON_POS[1] + math.sin(angle) * 50
    pygame.draw.line(screen, GRAY, CANNON_POS, (end_x, end_y), 20)
    return angle, end_x, end_y

def spawn_ball(ball_type, x, y, vx, vy, is_manual=False, inherited_mult=None):
    base = BALL_TYPES[ball_type]
    stats = ball_stats[ball_type] if ball_type in ball_stats else ball_stats["Regular"]
    
    final_bounce = min(0.98, base['base_bounce'] + stats['bounce_bonus'])
    radius = 4 if ball_type == "Shrapnel" else BALL_RADIUS
    
    gets_buffs = (random.random() < 0.40)
    revive_stack = []
    
    if gets_buffs:
        for _ in range(stats.get('base_top_revives', 0)): revive_stack.append('top')
        for _ in range(stats.get('base_bounce_revives', 0)): revive_stack.append('bounce')
        random.shuffle(revive_stack)
        
    b_dict = {
        'type': ball_type, 'is_manual': is_manual,
        'x': x, 'y': y, 'vx': vx, 'vy': vy,
        'color': base['color'], 'grav': base['base_grav'],
        'bounce': final_bounce, 'radius': radius,
        'gold_mult': inherited_mult if inherited_mult else stats['gold_mult'],
        'revive_stack': revive_stack 
    }
    
    if ball_type == 'Magic':
        b_dict['lightning_strikes'] = 2
        b_dict['lightning_timer'] = FPS * 1.5 
        b_dict['vy'] = 0.0 
        
    balls.append(b_dict)

def grant_peg_reward(peg, gold_mult, is_direct_hit=True, b_type=None):
    global cash, prestige_points, stat_points
    if peg['type'] == 'prestige':
        prestige_points += 3
        spawn_particles(peg['x'], peg['y'], BRONZE, count=20, speed=5.0)
        trigger_event("+3 PRESTIGE POINTS!")
    elif peg['type'] == 'stat':
        stat_points += 1
        spawn_particles(peg['x'], peg['y'], CYAN, count=30, speed=6.0)
        trigger_event("+1 STAT POINT!")
    elif peg['type'] == 'boss':
        cash += int(500 * gold_mult)
        spawn_particles(peg['x'], peg['y'], MAGENTA, count=40, speed=8.0)
        trigger_event("BOSS DEFEATED!")
    else:
        base_val = 10 if peg['type'] == 'gold' else (5 if peg['type'] in ['bomb', 'rainbow'] else 0)
        if base_val > 0: cash += int(base_val * gold_mult)
        
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
                trigger_event("GOLDEN SWARM!")
            elif event_roll == 2: 
                for _ in range(5): spawn_ball(b_type if b_type != 'Shrapnel' else 'Regular', peg['x'], peg['y'], random.uniform(-8, 8), random.uniform(-8, -2))
                trigger_event("MULTI-BALL FRENZY!")
            elif event_roll == 3: 
                jackpot_amt = int(500 * gold_mult)
                cash += jackpot_amt
                trigger_event(f"JACKPOT! +${jackpot_amt}")

def roll_crate(crate_name):
    crate = CRATES[crate_name]
    results = []
    
    for _ in range(crate['rolls']):
        r = random.random()
        if r < crate['odds']['Legendary']: rarity = 'Legendary'
        elif r < crate['odds']['Legendary'] + crate['odds']['Epic']: rarity = 'Epic'
        elif r < crate['odds']['Legendary'] + crate['odds']['Epic'] + crate['odds']['Rare']: rarity = 'Rare'
        else: rarity = 'Common'
        
        pool = [k for k,v in ABILITIES.items() if v['rarity'] == rarity]
        chosen = random.choice(pool)
        
        ability_inventory[chosen] += 1
        results.append({"name": chosen, "rarity": rarity})
            
    return results

# --- Draw Menus ---
def draw_main_menu():
    screen.fill(BLACK)
    pygame.draw.rect(screen, BROWN, (100, 100, WIDTH - 200, HEIGHT - 200), border_radius=10)
    pygame.draw.rect(screen, GOLD, (100, 100, WIDTH - 200, HEIGHT - 200), 3, border_radius=10)
    
    stats = ball_stats[equipped_ball]
    
    pygame.draw.rect(screen, TAN, (130, 130, WIDTH - 260, 160), border_radius=5)
    screen.blit(font_large.render(f"[{equipped_ball}] Lvl {stats['level']}", True, BLACK), (150, 140))
    screen.blit(font_med.render(f"GOLD: x{stats['gold_mult']:.1f}", True, BLACK), (150, 180))
    screen.blit(font_med.render(f"BOUNCE BONUS: +{stats['bounce_bonus']:.2f}", True, BLACK), (150, 210))
    screen.blit(font_med.render(f"MANUAL AMMO: {stats['max_balls']}", True, BLACK), (150, 240))
    
    btn_power = pygame.Rect(WIDTH//2 + 80, 140, 250, 40)
    pygame.draw.rect(screen, GREEN if cash >= stats['upg_cost_power'] else GRAY, btn_power, border_radius=5)
    screen.blit(font_med.render(f"Upg Power (${stats['upg_cost_power']})", True, BLACK), (btn_power.x + 10, btn_power.y + 10))

    btn_cap = pygame.Rect(WIDTH//2 + 80, 190, 250, 40)
    pygame.draw.rect(screen, GREEN if cash >= stats['upg_cost_balls'] else GRAY, btn_cap, border_radius=5)
    screen.blit(font_med.render(f"Upg Ammo (${stats['upg_cost_balls']})", True, BLACK), (btn_cap.x + 10, btn_cap.y + 10))

    btn_auto = pygame.Rect(WIDTH//2 + 80, 240, 250, 40)
    if stats['auto_drop_lvl'] >= 4:
        pygame.draw.rect(screen, GOLD, btn_auto, border_radius=5)
        screen.blit(font_med.render("Auto: MAXED", True, BLACK), (btn_auto.x + 10, btn_auto.y + 10))
    else:
        pygame.draw.rect(screen, GREEN if cash >= stats['upg_cost_auto'] else GRAY, btn_auto, border_radius=5)
        screen.blit(font_med.render(f"Upg Auto (${stats['upg_cost_auto']})", True, BLACK), (btn_auto.x + 10, btn_auto.y + 10))
        
    btn_special = None
    btn_top_rev = None
    btn_bot_rev = None
    
    top_lv = stats.get('base_top_revives', 0)
    bot_lv = stats.get('base_bounce_revives', 0)
    top_cost = top_lv + 1
    bot_cost = bot_lv + 1
    
    if not stats.get('special_unlocked'):
        btn_special = pygame.Rect(140, 255, 230, 30)
        pygame.draw.rect(screen, PURPLE if cash >= 20000 else GRAY, btn_special, border_radius=5)
        screen.blit(font_small.render("Unlock Special ($20k)", True, WHITE), (btn_special.x + 25, btn_special.y + 8))
    else:
        screen.blit(font_small.render(f"Top Revives: {top_lv}/5", True, DARK_BLUE), (140, 260))
        btn_top_rev = pygame.Rect(280, 255, 60, 25)
        if top_lv >= 5:
            pygame.draw.rect(screen, GOLD, btn_top_rev, border_radius=5)
            screen.blit(font_small.render("MAX", True, BLACK), (btn_top_rev.x + 12, btn_top_rev.y + 5))
        else:
            pygame.draw.rect(screen, CYAN if stat_points >= top_cost else GRAY, btn_top_rev, border_radius=5)
            screen.blit(font_small.render(f"{top_cost} SP", True, BLACK), (btn_top_rev.x + 10, btn_top_rev.y + 5))

        screen.blit(font_small.render(f"Bounce Rev: {bot_lv}/5", True, DARK_BLUE), (140, 285))
        btn_bot_rev = pygame.Rect(280, 280, 60, 25)
        if bot_lv >= 5:
            pygame.draw.rect(screen, GOLD, btn_bot_rev, border_radius=5)
            screen.blit(font_small.render("MAX", True, BLACK), (btn_bot_rev.x + 12, btn_bot_rev.y + 5))
        else:
            pygame.draw.rect(screen, GREEN if stat_points >= bot_cost else GRAY, btn_bot_rev, border_radius=5)
            screen.blit(font_small.render(f"{bot_cost} SP", True, BLACK), (btn_bot_rev.x + 10, btn_bot_rev.y + 5))
    
    card_rects = {} 
    visible_balls = {k: v for k, v in BALL_TYPES.items() if not v.get('hidden')}
    start_x = (WIDTH - (5 * 145)) // 2 + 10 
    start_y = 320
    
    for i, (b_name, b_data) in enumerate(visible_balls.items()):
        row, col = i // 5, i % 5
        card = pygame.Rect(start_x + (col * 145), start_y + (row * 135), 135, 125)
        card_rects[b_name] = card
        
        pygame.draw.rect(screen, TAN, card, border_radius=5)
        pygame.draw.rect(screen, GOLD if equipped_ball == b_name else BLACK, card, 3, border_radius=5)
        pygame.draw.circle(screen, b_data['color'], (card.x + 67, card.y + 25), 15)
        screen.blit(font_small.render(b_name, True, BLACK), (card.x + 10, card.y + 50))
        
        desc_words = b_data['desc'].split()
        if len(desc_words) > 2:
            screen.blit(font_tiny.render(" ".join(desc_words[:2]), True, DARK_GRAY), (card.x + 5, card.y + 70))
            screen.blit(font_tiny.render(" ".join(desc_words[2:]), True, DARK_GRAY), (card.x + 5, card.y + 85))
        else:
            screen.blit(font_tiny.render(b_data['desc'], True, DARK_GRAY), (card.x + 5, card.y + 75))
        
        if ball_stats[b_name]['unlocked']:
            screen.blit(font_small.render("EQUIPPED" if equipped_ball == b_name else "EQUIP", True, GREEN), (card.x + 15, card.y + 100))
        else:
            screen.blit(font_small.render(f"${b_data['cost']}", True, RED), (card.x + 15, card.y + 100))
        
    btn_view_tree = pygame.Rect(130, HEIGHT - 160, 250, 40)
    pygame.draw.rect(screen, PURPLE, btn_view_tree, border_radius=5)
    screen.blit(font_med.render("View Prestige Tree", True, WHITE), (btn_view_tree.x + 15, btn_view_tree.y + 10))

    btn_prestige_act = pygame.Rect(400, HEIGHT - 160, 280, 40)
    pygame.draw.rect(screen, BRONZE, btn_prestige_act, border_radius=5)
    screen.blit(font_med.render("PRESTIGE & RESTART", True, BLACK), (btn_prestige_act.x + 15, btn_prestige_act.y + 10))
    
    btn_abilities = pygame.Rect(700, HEIGHT - 160, 180, 40)
    pygame.draw.rect(screen, LIGHT_BLUE, btn_abilities, border_radius=5)
    screen.blit(font_med.render("Abilities", True, BLACK), (btn_abilities.x + 35, btn_abilities.y + 10))

    close_rect = pygame.Rect(WIDTH - 210, HEIGHT - 160, 80, 40)
    pygame.draw.rect(screen, RED, close_rect, border_radius=5)
    screen.blit(font_med.render("Back", True, WHITE), (close_rect.x + 12, close_rect.y + 10))
    
    return btn_power, btn_cap, btn_auto, close_rect, card_rects, btn_view_tree, btn_prestige_act, btn_abilities, btn_special, btn_top_rev, btn_bot_rev

def draw_abilities_menu():
    screen.fill(BLACK)
    pygame.draw.rect(screen, DARK_GRAY, (150, 30, WIDTH - 300, HEIGHT - 60), border_radius=10)
    pygame.draw.rect(screen, LIGHT_BLUE, (150, 30, WIDTH - 300, HEIGHT - 60), 3, border_radius=10)
    
    screen.blit(font_large.render("--- ACTIVE ABILITIES ---", True, LIGHT_BLUE), (WIDTH//2 - 200, 50))
    screen.blit(font_med.render(f"Equipped: {len(equipped_abilities)} / 5", True, WHITE), (WIDTH//2 - 90, 90))
    
    a_rects = {}
    start_x, start_y = 180, 130
    
    for i, (a_name, a_data) in enumerate(ABILITIES.items()):
        col = i % 2
        row = i // 2
        card = pygame.Rect(start_x + (col * 430), start_y + (row * 90), 410, 80)
        a_rects[a_name] = card
        
        pygame.draw.rect(screen, BLACK, card, border_radius=5)
        rarity_color = RARITY_COLORS[a_data['rarity']]
        pygame.draw.rect(screen, rarity_color, card, 2, border_radius=5)
        
        if a_name in equipped_abilities:
            pygame.draw.rect(screen, GREEN, card, 4, border_radius=5)
            screen.blit(font_med.render("EQ", True, GREEN), (card.x + card.width - 45, card.y + 25))
            
        screen.blit(font_med.render(a_name, True, a_data['color']), (card.x + 15, card.y + 10))
        
        tokens = ability_inventory.get(a_name, 0)
        t_color = WHITE if tokens > 0 else RED
        screen.blit(font_small.render(f"Tokens: {tokens}", True, t_color), (card.x + 15, card.y + 45))
        
        desc_words = a_data['desc'].split()
        screen.blit(font_tiny.render(" ".join(desc_words[:5]), True, GRAY), (card.x + 175, card.y + 20))
        screen.blit(font_tiny.render(" ".join(desc_words[5:]), True, GRAY), (card.x + 175, card.y + 40))

    btn_crates = pygame.Rect(180, HEIGHT - 90, 220, 40)
    pygame.draw.rect(screen, GOLD, btn_crates, border_radius=5)
    screen.blit(font_med.render("Buy Crates", True, BLACK), (btn_crates.x + 40, btn_crates.y + 10))

    btn_unequip = pygame.Rect(WIDTH//2 - 100, HEIGHT - 90, 200, 40)
    pygame.draw.rect(screen, RED, btn_unequip, border_radius=5)
    screen.blit(font_med.render("Unequip All", True, WHITE), (btn_unequip.x + 35, btn_unequip.y + 10))

    btn_close = pygame.Rect(WIDTH - 280, 50, 100, 40)
    pygame.draw.rect(screen, RED, btn_close, border_radius=5)
    screen.blit(font_med.render("Back", True, WHITE), (btn_close.x + 20, btn_close.y + 10))
    
    return a_rects, btn_unequip, btn_crates, btn_close

def draw_crates_menu():
    screen.fill(BLACK)
    pygame.draw.rect(screen, DARK_BLUE, (100, 50, WIDTH - 200, HEIGHT - 100), border_radius=10)
    pygame.draw.rect(screen, GOLD, (100, 50, WIDTH - 200, HEIGHT - 100), 3, border_radius=10)
    
    screen.blit(font_huge.render("ABILITY CRATES", True, GOLD), (WIDTH//2 - 250, 80))
    screen.blit(font_med.render(f"Current Cash: ${cash}", True, WHITE), (WIDTH//2 - 120, 150))
    
    c_rects = {}
    box_w = 260
    spacing = (WIDTH - 200 - (3 * box_w)) // 4
    start_x = 100 + spacing
    
    for i, (c_name, c_data) in enumerate(CRATES.items()):
        card = pygame.Rect(start_x + i*(box_w + spacing), 220, box_w, 350)
        c_rects[c_name] = card
        
        pygame.draw.rect(screen, BLACK, card, border_radius=10)
        pygame.draw.rect(screen, c_data['color'], card, 4, border_radius=10)
        
        screen.blit(font_large.render(c_name.split()[0], True, c_data['color']), (card.x + 50, card.y + 20))
        screen.blit(font_large.render(c_name.split()[1], True, c_data['color']), (card.x + 70, card.y + 60))
        
        screen.blit(font_med.render(f"Cost: ${c_data['cost']}", True, GOLD), (card.x + 40, card.y + 120))
        screen.blit(font_med.render(f"Rolls: {c_data['rolls']}", True, WHITE), (card.x + 85, card.y + 160))
        
        screen.blit(font_small.render("Drop Rates:", True, GRAY), (card.x + 20, card.y + 210))
        y_off = 240
        for rarity in ['Common', 'Rare', 'Epic', 'Legendary']:
            pct = int(c_data['odds'][rarity] * 100)
            screen.blit(font_small.render(f"{rarity}: {pct}%", True, RARITY_COLORS[rarity]), (card.x + 20, card.y + y_off))
            y_off += 25
            
        buy_rect = pygame.Rect(card.x + 30, card.y + 360, 200, 40)
        c_rects[c_name + "_buy"] = buy_rect
        pygame.draw.rect(screen, GREEN if cash >= c_data['cost'] else GRAY, buy_rect, border_radius=5)
        screen.blit(font_med.render("BUY CRATE", True, BLACK), (buy_rect.x + 30, buy_rect.y + 10))

    btn_close = pygame.Rect(WIDTH//2 - 75, HEIGHT - 100, 150, 40)
    pygame.draw.rect(screen, RED, btn_close, border_radius=5)
    screen.blit(font_med.render("Back", True, WHITE), (btn_close.x + 40, btn_close.y + 10))
    
    return c_rects, btn_close

def draw_prestige_tree(mx, my):
    screen.fill(DARK_BG)
    for node in tree_nodes:
        is_unlocked = p_upgrades.get(node['key'], 0) >= node['level']
        line_color = GREEN if is_unlocked else RED
        pygame.draw.line(screen, line_color, (node['prev_x'], node['prev_y']), (node['x'], node['y']), 3)
        
    pygame.draw.circle(screen, GOLD, (int(tree_center[0]), int(tree_center[1])), 25)
    pygame.draw.circle(screen, WHITE, (int(tree_center[0]), int(tree_center[1])), 25, 3)
    c_txt = font_tiny.render("CORE", True, BLACK)
    screen.blit(c_txt, (tree_center[0] - c_txt.get_width()//2, tree_center[1] - c_txt.get_height()//2))

    hovered_node = None
    for node in tree_nodes:
        lvl = p_upgrades.get(node['key'], 0)
        is_unlocked = lvl >= node['level']
        is_next = lvl == node['level'] - 1
        
        if is_unlocked: fill, border = node['color'], GREEN
        elif is_next: fill, border = BLACK, GOLD
        else: fill, border = BLACK, DARK_GRAY
            
        pygame.draw.circle(screen, fill, (int(node['x']), int(node['y'])), 16)
        pygame.draw.circle(screen, border, (int(node['x']), int(node['y'])), 16, 3)
        
        if math.hypot(mx - node['x'], my - node['y']) <= 16:
            hovered_node = node
            pygame.draw.circle(screen, WHITE, (int(node['x']), int(node['y'])), 16, 4)

    pygame.draw.circle(screen, BRONZE, (40, 40), 25)
    pp_txt = font_large.render(f"{prestige_points} PP", True, BRONZE)
    screen.blit(pp_txt, (75, 25))
    
    btn_close = pygame.Rect(WIDTH - 120, 20, 100, 40)
    pygame.draw.rect(screen, RED, btn_close, border_radius=5)
    screen.blit(font_med.render("CLOSE", True, WHITE), (btn_close.x + 10, btn_close.y + 10))

    if hovered_node:
        data = PRESTIGE_DEFS[hovered_node['key']]
        clvl = p_upgrades.get(hovered_node['key'], 0)
        if clvl >= hovered_node['level']: stat_str = "(Purchased)"
        elif clvl == hovered_node['level'] - 1: stat_str = f"(Cost: {hovered_node['cost']} PP)"
        else: stat_str = "(Locked)"
            
        tt_width, tt_height = 240, 90
        tt_x, tt_y = mx + 15, my + 15
        if tt_x + tt_width > WIDTH: tt_x = mx - tt_width - 15 
        if tt_y + tt_height > HEIGHT: tt_y = my - tt_height - 15
        
        pygame.draw.rect(screen, TAN, (tt_x, tt_y, tt_width, tt_height), border_radius=5)
        pygame.draw.rect(screen, BLACK, (tt_x, tt_y, tt_width, tt_height), 2, border_radius=5)
        
        screen.blit(font_small.render(f"{data['name']} Lvl {hovered_node['level']}", True, BLACK), (tt_x + 10, tt_y + 10))
        screen.blit(font_small.render(stat_str, True, DARK_GRAY), (tt_x + 10, tt_y + 35))
        screen.blit(font_small.render(data['desc'], True, BLACK), (tt_x + 10, tt_y + 60))
        
    return btn_close, hovered_node

# --- Main Game Loop ---
running = True
while running:
    mx, my = pygame.mouse.get_pos()
    active_pegs = [p for p in pegs if p['active']]
    
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            save_game()
            running = False
            
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if state == "OFFLINE_SCREEN":
                btn_collect = pygame.Rect(WIDTH//2 - 100, HEIGHT - 150, 200, 60)
                if btn_collect.collidepoint(mx, my):
                    cash += offline_rewards['cash']
                    prestige_points += offline_rewards['pp']
                    stat_points += offline_rewards['sp']
                    last_save_time = time.time()
                    save_game()
                    state = "PLAY"
                    
            elif state == "CRATE_REWARD":
                btn_ok = pygame.Rect(WIDTH//2 - 75, HEIGHT - 150, 150, 50)
                if btn_ok.collidepoint(mx, my):
                    state = "CRATES_MENU"
                    save_game()

            elif state == "PLAY" and board_clear_timer == 0:
                clicked_ui = False
                
                if WIDTH - 120 <= mx <= WIDTH - 20 and 20 <= my <= 60:
                    state = "MENU"
                    clicked_ui = True
                elif WIDTH - 260 <= mx <= WIDTH - 130 and 20 <= my <= 60 and ball_stats[equipped_ball]['auto_drop_lvl'] > 0:
                    ball_stats[equipped_ball]['auto_enabled'] = not ball_stats[equipped_ball]['auto_enabled']
                    save_game()
                    clicked_ui = True
                
                if equipped_abilities and not clicked_ui:
                    for i, a_name in enumerate(equipped_abilities):
                        ab_rect = pygame.Rect(20, HEIGHT - 70 - (i * 60), 290, 50)
                        if ab_rect.collidepoint(mx, my):
                            clicked_ui = True
                            
                            if a_name in ['Fire Cursor', 'Vacuum Cursor']:
                                if active_ability_mode == a_name:
                                    active_ability_mode = None
                                elif ability_inventory.get(a_name, 0) > 0:
                                    ability_inventory[a_name] -= 1
                                    active_ability_mode = a_name
                                    if a_name == 'Fire Cursor': fire_cursor_timer = FPS * 5
                                    if a_name == 'Vacuum Cursor': vacuum_cursor_timer = FPS * 5
                                    
                            elif a_name == 'Starfall':
                                if ability_inventory.get(a_name, 0) > 0:
                                    ability_inventory[a_name] -= 1
                                    for _ in range(10):
                                        spawn_ball('Bouncy', random.randint(50, WIDTH-50), 20, random.uniform(-5, 5), 0)
                                    active_ability_mode = None
                            elif a_name == 'Drone':
                                if ability_inventory.get(a_name, 0) > 0:
                                    ability_inventory[a_name] -= 1
                                    drones.append({'x': WIDTH//2, 'y': -20, 'state': 'collecting', 'balls': [], 'target': None})
                                    active_ability_mode = None
                            elif a_name == 'Revive Wave':
                                if ability_inventory.get(a_name, 0) > 0 and balls:
                                    ability_inventory[a_name] -= 1
                                    for b in balls:
                                        if 'revive_stack' not in b: b['revive_stack'] = []
                                        b['revive_stack'].insert(random.randint(0, len(b['revive_stack'])), 'top')
                                        spawn_particles(b['x'], b['y'], CYAN, count=15, speed=5.0)
                                    if bounce_sound: bounce_sound.play()
                                    active_ability_mode = None
                            elif a_name == 'Bounce Revive':
                                if ability_inventory.get(a_name, 0) > 0 and balls:
                                    ability_inventory[a_name] -= 1
                                    for b in balls:
                                        if 'revive_stack' not in b: b['revive_stack'] = []
                                        b['revive_stack'].insert(random.randint(0, len(b['revive_stack'])), 'bounce')
                                        spawn_particles(b['x'], b['y'], GREEN, count=15, speed=5.0)
                                    if bounce_sound: bounce_sound.play()
                                    active_ability_mode = None
                                    
                            else:
                                if active_ability_mode == a_name:
                                    active_ability_mode = None 
                                elif ability_inventory.get(a_name, 0) > 0:
                                    active_ability_mode = a_name 
                            break
                
                if not clicked_ui:
                    active_drones = [d for d in drones if d['state'] in ['collecting', 'holding']]
                    
                    if active_drones and my < HEIGHT - 80:
                        for d in active_drones:
                            d['state'] = 'delivering'
                            d['drop_x'] = mx
                            d['drop_y'] = my
                        if bounce_sound: bounce_sound.play()
                        
                    elif active_ability_mode == 'Thunder Cloud':
                        if ability_inventory.get('Thunder Cloud', 0) > 0 and my < HEIGHT - 80:
                            ability_inventory['Thunder Cloud'] -= 1
                            clouds.append({'x': mx, 'y': my, 'timer': FPS * 1, 'struck': False})
                            active_ability_mode = None 
                            
                    elif active_ability_mode == 'Black Hole':
                        if ability_inventory.get('Black Hole', 0) > 0 and my < HEIGHT - 80:
                            ability_inventory['Black Hole'] -= 1
                            black_holes.append({'x': mx, 'y': my, 'vx': random.uniform(-1.5, 1.5), 'vy': random.uniform(-1.5, 1.5), 'timer': FPS * 6, 'radius': 200})
                            active_ability_mode = None
                            
                    elif active_ability_mode == 'Midas Touch':
                        if ability_inventory.get('Midas Touch', 0) > 0 and my < HEIGHT - 80:
                            ability_inventory['Midas Touch'] -= 1
                            spawn_particles(mx, my, GOLD, count=30, speed=8.0)
                            if bounce_sound: bounce_sound.play()
                            for peg in pegs:
                                if peg['active'] and math.hypot(peg['x'] - mx, peg['y'] - my) < 80 and peg['type'] not in ['boss', 'stat']: 
                                    peg['type'] = 'gold'
                                    peg['on_fire'] = False 
                            active_ability_mode = None
                            
                    elif active_ability_mode == 'Orbital Strike':
                        if ability_inventory.get('Orbital Strike', 0) > 0 and my < HEIGHT - 80:
                            ability_inventory['Orbital Strike'] -= 1
                            lasers.append({'x': mx, 'timer': FPS * 1})
                            if bounce_sound: bounce_sound.play()
                            for peg in pegs:
                                if peg['active'] and abs(peg['x'] - mx) < 45:
                                    if peg['type'] == 'boss':
                                        peg['hp'] -= 3 
                                        spawn_particles(peg['x'], peg['y'], MAGENTA, count=10, speed=5.0)
                                        if peg['hp'] <= 0:
                                            peg['active'] = False
                                            grant_peg_reward(peg, 1.0, is_direct_hit=True)
                                    else:
                                        peg['active'] = False
                                        grant_peg_reward(peg, 1.0, is_direct_hit=False)
                                        spawn_particles(peg['x'], peg['y'], RED, count=5, speed=10.0)
                            active_ability_mode = None
                            
                    elif active_ability_mode in ['Fire Cursor', 'Vacuum Cursor']:
                        pass 
                        
                    else:
                        manual_balls = len([b for b in balls if b['is_manual'] and b['type'] == equipped_ball])
                        if manual_balls < ball_stats[equipped_ball]['max_balls'] and my > 70: 
                            angle, spawn_x, spawn_y = draw_cannon(mx, my)
                            if math.sin(angle) > 0: 
                                shots = 1 + p_upgrades.get('multishot', 0)
                                for s in range(shots):
                                    spread = (s - (shots-1)/2.0) * 0.15
                                    s_angle = angle + spread
                                    spawn_ball(equipped_ball, spawn_x, spawn_y, math.cos(s_angle) * 10, math.sin(s_angle) * 10, is_manual=True)
                        
            elif state == "MENU":
                btn_power, btn_cap, btn_auto, close_btn, card_rects, btn_view_tree, btn_prestige_act, btn_abilities, btn_special, btn_top_rev, btn_bot_rev = draw_main_menu()
                stats = ball_stats[equipped_ball]
                
                if close_btn.collidepoint(mx, my):
                    state = "PLAY"
                    save_game()
                elif btn_view_tree.collidepoint(mx, my):
                    state = "PRESTIGE_TREE"
                    view_only_tree = True 
                elif btn_prestige_act.collidepoint(mx, my):
                    state = "CONFIRM_PRESTIGE"
                elif btn_abilities.collidepoint(mx, my):
                    state = "ABILITIES_MENU"
                    
                elif btn_special and btn_special.collidepoint(mx, my) and cash >= 20000:
                    cash -= 20000
                    stats['special_unlocked'] = True
                    save_game()
                elif btn_top_rev and btn_top_rev.collidepoint(mx, my):
                    top_lv = stats.get('base_top_revives', 0)
                    cost = top_lv + 1
                    if stat_points >= cost and top_lv < 5:
                        stat_points -= cost
                        stats['base_top_revives'] = top_lv + 1
                        save_game()
                elif btn_bot_rev and btn_bot_rev.collidepoint(mx, my):
                    bot_lv = stats.get('base_bounce_revives', 0)
                    cost = bot_lv + 1
                    if stat_points >= cost and bot_lv < 5:
                        stat_points -= cost
                        stats['base_bounce_revives'] = bot_lv + 1
                        save_game()
                    
                elif btn_power.collidepoint(mx, my) and cash >= stats['upg_cost_power']:
                    cash -= stats['upg_cost_power']
                    stats['level'] += 1; stats['gold_mult'] += 0.5; stats['bounce_bonus'] += 0.02
                    stats['upg_cost_power'] = int(stats['upg_cost_power'] * 1.5)
                elif btn_cap.collidepoint(mx, my) and cash >= stats['upg_cost_balls']:
                    cash -= stats['upg_cost_balls']
                    stats['max_balls'] += 1
                    stats['upg_cost_balls'] = int(stats['upg_cost_balls'] * 2.5)
                elif btn_auto.collidepoint(mx, my) and cash >= stats['upg_cost_auto'] and stats['auto_drop_lvl'] < 4:
                    cash -= stats['upg_cost_auto']
                    stats['auto_drop_lvl'] += 1
                    stats['upg_cost_auto'] = int(stats['upg_cost_auto'] * 3.0)
                    
                for b_name, rect in card_rects.items():
                    if rect.collidepoint(mx, my):
                        if ball_stats[b_name]['unlocked']:
                            equipped_ball = b_name
                        elif cash >= BALL_TYPES[b_name]['cost']:
                            cash -= BALL_TYPES[b_name]['cost']
                            ball_stats[b_name]['unlocked'] = True
                            equipped_ball = b_name
                            
            elif state == "ABILITIES_MENU":
                a_rects, btn_unequip, btn_crates, btn_close = draw_abilities_menu()
                if btn_close.collidepoint(mx, my):
                    state = "MENU"
                    save_game()
                elif btn_crates.collidepoint(mx, my):
                    state = "CRATES_MENU"
                elif btn_unequip.collidepoint(mx, my):
                    equipped_abilities.clear()
                    active_ability_mode = None
                else:
                    for a_name, rect in a_rects.items():
                        if rect.collidepoint(mx, my):
                            if a_name in equipped_abilities:
                                equipped_abilities.remove(a_name)
                                if active_ability_mode == a_name: active_ability_mode = None
                            elif len(equipped_abilities) < 5:
                                equipped_abilities.append(a_name)

            elif state == "CRATES_MENU":
                c_rects, btn_close = draw_crates_menu()
                if btn_close.collidepoint(mx, my):
                    state = "ABILITIES_MENU"
                else:
                    for c_name, c_data in CRATES.items():
                        buy_key = c_name + "_buy"
                        if buy_key in c_rects and c_rects[buy_key].collidepoint(mx, my):
                            if cash >= c_data['cost']:
                                cash -= c_data['cost']
                                crate_results_display = roll_crate(c_name)
                                state = "CRATE_REWARD"

            elif state == "CONFIRM_PRESTIGE":
                yes_rect = pygame.Rect(WIDTH//2 - 150, HEIGHT//2 + 20, 100, 50)
                no_rect = pygame.Rect(WIDTH//2 + 50, HEIGHT//2 + 20, 100, 50)
                if yes_rect.collidepoint(mx, my):
                    perform_prestige_reset()
                    state = "PRESTIGE_TREE"
                    view_only_tree = False 
                elif no_rect.collidepoint(mx, my):
                    state = "MENU"

            elif state == "PRESTIGE_TREE":
                btn_close, hovered_node = draw_prestige_tree(mx, my)
                
                if btn_close.collidepoint(mx, my):
                    state = "MENU" if view_only_tree else "PLAY"
                    save_game()
                    
                elif hovered_node and not view_only_tree:
                    if p_upgrades.get(hovered_node['key'], 0) == hovered_node['level'] - 1:
                        if prestige_points >= hovered_node['cost']:
                            prestige_points -= hovered_node['cost']
                            p_upgrades[hovered_node['key']] += 1
                            active_coords = [(p['x'], p['y']) for p in pegs if p['active']]
                            populate_pegs(active_coords)

    if state == "PLAY":
        screen.fill(BLACK)
        
        # --- DRONE LOGIC ---
        for d in drones[:]:
            if d['state'] == 'collecting':
                if len(d['balls']) >= 10:
                    d['state'] = 'holding'
                    d['target'] = None
                elif not d.get('target') or d['target'] not in balls:
                    if balls:
                        d['target'] = random.choice(balls)
                    else:
                        d['target'] = None

                if d['target'] and d['target'] in balls:
                    # TRACTOR BEAM: Slow the ball down so it can't escape!
                    d['target']['vx'] *= 0.5
                    d['target']['vy'] *= 0.5
                    
                    dx, dy = d['target']['x'] - d['x'], d['target']['y'] - d['y']
                    dist = math.hypot(dx, dy)
                    speed = 15.0 # Sped the drone up a bit too
                    if dist < speed:
                        d['x'], d['y'] = d['target']['x'], d['target']['y']
                        d['balls'].append(d['target'])
                        if d['target'] in balls: balls.remove(d['target'])
                        d['target'] = None
                    else:
                        d['x'] += (dx/dist) * speed
                        d['y'] += (dy/dist) * speed
                else:
                    # Hover if no balls found
                    d['y'] = max(60, d['y'] - 2)
                    d['target'] = None # Clear target if it fell off screen
                    
            elif d['state'] == 'holding':
                # Hover in place and wait for click
                d['y'] = max(60, d['y'] - 2)
                
            elif d['state'] == 'delivering':
                dx, dy = d['drop_x'] - d['x'], d['drop_y'] - d['y']
                dist = math.hypot(dx, dy)
                speed = 15.0
                if dist < speed:
                    # Drop payload
                    for b in d['balls']:
                        b['x'], b['y'] = d['x'], d['y']
                        b['vx'] = random.uniform(-4, 4)
                        b['vy'] = random.uniform(-2, 4)
                        balls.append(b)
                    spawn_particles(d['x'], d['y'], CYAN, 25, 6)
                    drones.remove(d)
                else:
                    d['x'] += (dx/dist) * speed
                    d['y'] += (dy/dist) * speed
                    
        # -------------------
        
        if active_ability_mode == 'Vacuum Cursor':
            vacuum_cursor_timer -= 1
            if vacuum_cursor_timer <= 0:
                active_ability_mode = None
            elif pygame.mouse.get_pressed()[0] and my < HEIGHT - 80:
                for b in balls:
                    dx, dy = mx - b['x'], my - b['y']
                    dist = math.hypot(dx, dy)
                    if dist < 200:
                        pull = min(5.0, 200 / max(dist, 1))
                        b['vx'] += (dx/dist) * pull * 0.2
                        b['vy'] += (dy/dist) * pull * 0.2
                        b['vx'] *= 0.95
                        b['vy'] *= 0.95
                        
        if active_ability_mode == 'Fire Cursor':
            fire_cursor_timer -= 1
            if fire_cursor_timer <= 0:
                active_ability_mode = None
            elif pygame.mouse.get_pressed()[0] and my < HEIGHT - 80:
                fire_ability_timer += 1
                if fire_ability_timer >= 2: 
                    fire_ability_timer = 0
                    spawn_particles(mx + random.uniform(-10, 10), my + random.uniform(-10, 10), ORANGE, count=2, speed=2.0)
                    for peg in active_pegs:
                        if not peg.get('on_fire') and peg['type'] not in ['boss', 'stat'] and math.hypot(peg['x'] - mx, peg['y'] - my) < 30:
                            peg['on_fire'] = True
                            peg['fire_timer'] = FPS * 4
                            peg['fire_mult'] = 1.0
                            peg['fire_budget_ref'] = [2] 

        for l in lasers[:]:
            l['timer'] -= 1
            if l['timer'] <= 0: lasers.remove(l)

        for bh in black_holes[:]:
            bh['timer'] -= 1
            bh['x'] += bh['vx']
            bh['y'] += bh['vy']
            
            if bh['x'] < 50 or bh['x'] > WIDTH - 50: bh['vx'] *= -1
            if bh['y'] < 50 or bh['y'] > HEIGHT - 100: bh['vy'] *= -1
            
            for peg in pegs:
                if peg['active']:
                    dx = bh['x'] - peg['x']
                    dy = bh['y'] - peg['y']
                    dist = math.hypot(dx, dy)
                    
                    if dist < bh['radius']:
                        pull_force = min(12.0, bh['radius'] / max(dist, 1)) 
                        if peg['type'] != 'boss':
                            peg['x'] += (dx / dist) * pull_force
                            peg['y'] += (dy / dist) * pull_force
                        
                        if dist < 20: 
                            if peg['type'] == 'boss':
                                peg['hp'] -= 1
                                if peg['hp'] <= 0:
                                    peg['active'] = False
                                    grant_peg_reward(peg, 2.0, is_direct_hit=True) 
                            else:
                                peg['active'] = False
                                grant_peg_reward(peg, 2.0, is_direct_hit=False) 
                                spawn_particles(peg['x'], peg['y'], PURPLE, count=5, speed=6.0)
                            if random.random() < 0.2 and bounce_sound: 
                                bounce_sound.play()
                                
            if bh['timer'] <= 0:
                black_holes.remove(bh)
        
        for c in clouds[:]:
            c['timer'] -= 1
            if c['timer'] <= FPS * 0.75 and not c['struck']:
                c['struck'] = True
                target = None
                min_dist = float('inf')
                for p in active_pegs:
                    d = math.hypot(p['x'] - c['x'], p['y'] - c['y'])
                    if d < min_dist:
                        min_dist = d
                        target = p
                        
                if target:
                    lightnings.append({'start': (c['x'], c['y'] + 10), 'end': (target['x'], target['y']), 'life': 10})
                    if bounce_sound: bounce_sound.play()
                    
                    if target['type'] == 'boss':
                        target['hp'] -= 1
                        spawn_particles(target['x'], target['y'], MAGENTA, count=10, speed=5.0)
                        if target['hp'] <= 0:
                            target['active'] = False
                            grant_peg_reward(target, 1.0, is_direct_hit=True)
                    else:
                        target['on_fire'] = True
                        target['fire_timer'] = FPS * 4
                        target['fire_budget_ref'] = [8] 
                        target['fire_mult'] = 1.0 
                        
                        for other in pegs:
                            if other['active'] and other['type'] not in ['boss', 'stat'] and not other.get('on_fire'):
                                if math.hypot(other['x'] - target['x'], other['y'] - target['y']) < 60:
                                    other['on_fire'] = True
                                    other['fire_timer'] = FPS * 4
                                    other['fire_mult'] = 1.0
                                    node_budget = target['fire_budget_ref']
                                    other['fire_budget_ref'] = node_budget
                                    node_budget[0] -= 1
            if c['timer'] <= 0:
                clouds.remove(c)
        
        if board_clear_timer == 0:
            for peg in pegs:
                if peg['active'] and peg.get('on_fire'):
                    peg['fire_timer'] -= 1
                    if random.random() < 0.1: 
                        spawn_particles(peg['x'], peg['y'], ORANGE, count=1, speed=2.0)
                        
                    if random.random() < 0.05 and peg.get('fire_budget_ref', [0])[0] > 0:
                        for other in pegs:
                            if other['active'] and other['type'] not in ['boss', 'stat'] and not other.get('on_fire'):
                                if math.hypot(peg['x'] - other['x'], peg['y'] - other['y']) < 65:
                                    other['on_fire'] = True
                                    other['fire_timer'] = FPS * 4
                                    other['fire_mult'] = peg.get('fire_mult', 1.0)
                                    node_budget = peg['fire_budget_ref']
                                    other['fire_budget_ref'] = node_budget 
                                    node_budget[0] -= 1 
                                    break 
                                    
                    if peg['fire_timer'] <= 0:
                        peg['active'] = False
                        if bounce_sound: bounce_sound.play()
                        grant_peg_reward(peg, peg.get('fire_mult', 1.0), is_direct_hit=False)

        if board_clear_timer == 0:
            for b_name, b_stat in ball_stats.items():
                if b_stat['unlocked'] and b_stat['auto_drop_lvl'] > 0 and b_stat.get('auto_enabled', True):
                    b_stat['auto_timer'] += 1
                    rate = get_auto_drop_rate(b_stat['auto_drop_lvl'])
                    if b_stat['auto_timer'] >= rate * FPS:
                        b_stat['auto_timer'] = 0
                        if active_pegs and random.random() < 0.8:
                            target_peg = random.choice(active_pegs)
                            spawn_x = target_peg['x'] + random.uniform(-15, 15)
                        else:
                            spawn_x = random.randint(20, WIDTH-20)
                        spawn_ball(b_name, spawn_x, 20.0, random.uniform(-1, 1), 0.0)
        
        for b in balls[:]:
            if b['type'] == 'Wood':
                b['wood_timer'] = b.get('wood_timer', 0) + 1
                if b['wood_timer'] >= FPS * 1.5: 
                    b['wood_timer'] = 0
                    cash += int(10 * b['gold_mult'])
                    spawn_particles(b['x'], b['y'], GREEN, count=3, speed=2.0)
                    
            b['vy'] += b['grav'] 
            b['x'] += b['vx']
            b['y'] += b['vy']
            
            speed = math.hypot(b['vx'], b['vy'])
            max_speed = 18.0
            if speed > max_speed:
                b['vx'] = (b['vx'] / speed) * max_speed
                b['vy'] = (b['vy'] / speed) * max_speed
                
            if b['type'] == 'Magic' and b.get('lightning_strikes', 0) > 0:
                b['lightning_timer'] -= 1
                if b['lightning_timer'] <= 0:
                    below_targets = [p for p in active_pegs if p['y'] > b['y']]
                    target = random.choice(below_targets) if below_targets else (random.choice(active_pegs) if active_pegs else None)
                    if target:
                        lightnings.append({'start': (b['x'], b['y']), 'end': (target['x'], target['y']), 'life': 10})
                        if bounce_sound: bounce_sound.play()
                        
                        if target['type'] == 'boss':
                            target['hp'] -= 1
                            spawn_particles(target['x'], target['y'], MAGENTA, count=10, speed=5.0)
                            if target['hp'] <= 0:
                                target['active'] = False
                                grant_peg_reward(target, b['gold_mult'], is_direct_hit=True)
                        else:
                            target['on_fire'] = True
                            target['fire_timer'] = FPS * 4
                            target['fire_budget_ref'] = [5] 
                            target['fire_mult'] = b['gold_mult']
                            
                            for other in pegs:
                                if other['active'] and other['type'] not in ['boss', 'stat'] and not other.get('on_fire'):
                                    if math.hypot(other['x'] - target['x'], other['y'] - target['y']) < 60:
                                        other['on_fire'] = True
                                        other['fire_timer'] = FPS * 4
                                        other['fire_mult'] = b['gold_mult']
                                        node_budget = target['fire_budget_ref']
                                        other['fire_budget_ref'] = node_budget
                                        node_budget[0] -= 1
                                    
                        b['lightning_strikes'] -= 1
                        b['lightning_timer'] = FPS * 1.5 
                        
                        if b['lightning_strikes'] <= 0:
                            b['type'] = 'Regular'
                            b['color'] = BALL_TYPES['Regular']['color']
                            b['grav'] = BALL_TYPES['Regular']['base_grav']
                            b['bounce'] = BALL_TYPES['Regular']['base_bounce'] + ball_stats['Regular']['bounce_bonus']
            
            rad = b.get('radius', BALL_RADIUS)
            
            if b['x'] - rad < 0 or b['x'] + rad > WIDTH:
                b['x'] = rad if b['x'] - rad < 0 else WIDTH - rad
                b['vx'] *= -b['bounce']
                if bounce_sound: bounce_sound.play()
                
                if b['type'] == 'Regular': 
                    cash += 5
                    spawn_particles(b['x'], b['y'], GOLD, count=3)
                elif b['type'] == 'Bouncy':
                    b['gold_mult'] += 0.5
                    spawn_particles(b['x'], b['y'], CYAN, count=5)
                
            if b['y'] - rad > HEIGHT:
                
                if b.get('revive_stack'):
                    rev_type = b['revive_stack'].pop()
                    if rev_type == 'top':
                        b['y'] = 40
                        b['vy'] = 0.0
                        spawn_particles(b['x'], b['y'], CYAN, count=15, speed=6.0)
                        if bounce_sound: bounce_sound.play()
                        continue
                    elif rev_type == 'bounce':
                        b['y'] = HEIGHT - rad - 5
                        b['vy'] = -15.0
                        spawn_particles(b['x'], b['y'], GREEN, count=15, speed=6.0)
                        if bounce_sound: bounce_sound.play()
                        continue
                    
                if b['type'] == 'Maroon' and not b.get('bottom_bounced'):
                    b['y'] = HEIGHT - rad - 5
                    b['vy'] = -15.0
                    b['bottom_bounced'] = True
                    if bounce_sound: bounce_sound.play()
                    continue
                if b['type'] == 'Hoops' and not b.get('teleported'):
                    b['y'] = 40
                    b['vy'] = 0.0
                    b['teleported'] = True
                    spawn_particles(b['x'], HEIGHT, ORANGE, count=10)
                    continue
                if b['type'] == 'Boulder':
                    if active_pegs:
                        targets = random.sample(active_pegs, min(3, len(active_pegs)))
                        for t in targets:
                            if t['type'] == 'boss':
                                t['hp'] -= 1
                                if t['hp'] <= 0:
                                    t['active'] = False
                                    grant_peg_reward(t, b['gold_mult'], True, 'Boulder')
                            else:
                                t['active'] = False
                                grant_peg_reward(t, b['gold_mult'], True, 'Boulder')
                        if bounce_sound: bounce_sound.play()
                        
                balls.remove(b) 
                continue 
            
            for bmp in bumpers:
                dx, dy = b['x'] - bmp['x'], b['y'] - bmp['y']
                dist = math.hypot(dx, dy)
                if dist < rad + bmp['radius']:
                    if bounce_sound: bounce_sound.play()
                    if dist == 0: dist = 0.1
                    nx, ny = dx / dist, dy / dist
                    b['x'] += nx * ((rad + bmp['radius']) - dist)
                    b['y'] += ny * ((rad + bmp['radius']) - dist)
                    dot = b['vx'] * nx + b['vy'] * ny
                    b['vx'] = (b['vx'] - 2 * dot * nx) * min(0.98, b['bounce'] * 1.1)
                    b['vy'] = (b['vy'] - 2 * dot * ny) * min(0.98, b['bounce'] * 1.1)

            for peg in pegs:
                if peg['active']:
                    dx, dy = b['x'] - peg['x'], b['y'] - peg['y']
                    dist = math.hypot(dx, dy)
                    
                    p_rad = PEG_RADIUS * 1.5 if peg['type'] == 'boss' else PEG_RADIUS
                    
                    if dist < rad + p_rad:
                        
                        if peg['type'] == 'boss':
                            peg['hp'] -= 1
                            spawn_particles(peg['x'], peg['y'], MAGENTA, count=10, speed=5.0)
                            if peg['hp'] <= 0:
                                peg['active'] = False
                                grant_peg_reward(peg, b['gold_mult'], True, b['type'])
                        elif peg['type'] == 'stat':
                            peg['active'] = False
                            grant_peg_reward(peg, b['gold_mult'], True, b['type'])
                        else:
                            if b['type'] == 'Fire':
                                if not peg.get('on_fire'):
                                    peg['on_fire'] = True
                                    peg['fire_timer'] = FPS * 4
                                    peg['fire_mult'] = b['gold_mult'] 
                                    peg['fire_budget_ref'] = [random.randint(4, 6)] 
                                    
                            elif b['type'] == 'Bomb':
                                peg['active'] = False
                                grant_peg_reward(peg, b['gold_mult'], True, b['type'])
                                spawn_particles(peg['x'], peg['y'], DARK_BLUE, count=15, speed=6.0)
                                for _ in range(8):
                                    spawn_ball('Shrapnel', peg['x'], peg['y'], random.uniform(-10, 10), random.uniform(-10, -2), inherited_mult=b['gold_mult'])
                                balls.remove(b)
                                break 
                            else:
                                peg['active'] = False
                                grant_peg_reward(peg, b['gold_mult'], True, b['type'])

                        if bounce_sound: bounce_sound.play()
                        if dist == 0: dist = 0.1 
                        nx, ny = dx / dist, dy / dist
                        b['x'] += nx * ((rad + p_rad) - dist)
                        b['y'] += ny * ((rad + p_rad) - dist)
                        dot = b['vx'] * nx + b['vy'] * ny
                        b['vx'] = (b['vx'] - 2 * dot * nx) * b['bounce']
                        b['vy'] = (b['vy'] - 2 * dot * ny) * b['bounce']
                        break 

        for p in particles[:]:
            p['x'] += p['vx']
            p['y'] += p['vy']
            p['life'] -= 1
            p['radius'] = max(0, p['radius'] - 0.1)
            if p['life'] <= 0: particles.remove(p)

        for l in lightnings[:]:
            l['life'] -= 1
            if l['life'] <= 0: lightnings.remove(l)

        if all(not p['active'] for p in pegs):
            if len(pegs) > 0 and board_clear_timer == 0:
                board_clear_timer = FPS * 2 
                cash += 100 
                boards_cleared += 1
                for _ in range(10): 
                    spawn_particles(random.randint(200, WIDTH-200), random.randint(200, HEIGHT-200), random.choice([GOLD, CYAN, RED, GREEN]), count=30, speed=8.0)
                save_game() 
        
        # --- Drawing ---
        for bmp in bumpers:
            points = [
                (bmp['x'], bmp['y'] - bmp['radius']), (bmp['x'] + bmp['radius'], bmp['y']),
                (bmp['x'], bmp['y'] + bmp['radius']), (bmp['x'] - bmp['radius'], bmp['y'])
            ]
            pygame.draw.polygon(screen, GRAY, points)
            pygame.draw.polygon(screen, WHITE, points, 2)
            
        for bh in black_holes:
            bh_x, bh_y = int(bh['x']), int(bh['y'])
            pulse = math.sin(pygame.time.get_ticks() / 150.0) * 15
            pygame.draw.circle(screen, PURPLE, (bh_x, bh_y), int(bh['radius'] + pulse), 2)
            pygame.draw.circle(screen, DARK_BLUE, (bh_x, bh_y), int((bh['radius'] * 0.7) + (pulse * 0.5)), 2)
            pygame.draw.circle(screen, BLACK, (bh_x, bh_y), 20)
            pygame.draw.circle(screen, PURPLE, (bh_x, bh_y), 20, 2) 

        fx_surface.fill((0,0,0,0)) 
        for c in clouds:
            alpha = min(255, int((c['timer'] / FPS) * 255))
            cx, cy = int(c['x']), int(c['y'])
            pygame.draw.circle(fx_surface, (*DARK_GRAY, alpha), (cx, cy), 35)
            pygame.draw.circle(fx_surface, (*DARK_GRAY, alpha), (cx - 25, cy + 15), 25)
            pygame.draw.circle(fx_surface, (*DARK_GRAY, alpha), (cx + 25, cy + 15), 25)
            
        for l in lasers:
            alpha = min(255, int((l['timer'] / FPS) * 255 * 2)) 
            lx = int(l['x'])
            pygame.draw.rect(fx_surface, (*RED, alpha), (lx - 45, 0, 90, HEIGHT))
            pygame.draw.rect(fx_surface, (*WHITE, alpha), (lx - 15, 0, 30, HEIGHT))
            
        screen.blit(fx_surface, (0, 0))
        
        for l in lightnings:
            pygame.draw.line(screen, PURPLE, l['start'], l['end'], 6)
            pygame.draw.line(screen, CYAN, l['start'], l['end'], 2)
        
        for peg in pegs:
            if peg['active']:
                if peg.get('on_fire'): color = ORANGE
                elif peg['type'] == 'rainbow': color = get_rainbow_color()
                elif peg['type'] == 'gold': color = GOLD
                elif peg['type'] == 'bomb': color = DARK_GRAY
                elif peg['type'] == 'prestige': color = BROWN
                elif peg['type'] == 'boss': color = MAGENTA
                elif peg['type'] == 'stat': color = CYAN
                else: color = GREEN
                
                if peg['type'] == 'boss':
                    pygame.draw.circle(screen, color, (int(peg['x']), int(peg['y'])), PEG_RADIUS * 1.5)
                    hp_txt = font_tiny.render(str(peg.get('hp', 0)), True, WHITE)
                    screen.blit(hp_txt, (peg['x'] - hp_txt.get_width()//2, peg['y'] - hp_txt.get_height()//2))
                else:
                    pygame.draw.circle(screen, color, (int(peg['x']), int(peg['y'])), PEG_RADIUS)
                
                if peg['type'] == 'bomb': pygame.draw.circle(screen, RED, (int(peg['x']), int(peg['y'])), 4)
                elif peg['type'] == 'prestige': pygame.draw.circle(screen, BRONZE, (int(peg['x']), int(peg['y'])), 6, 2)
                elif peg['type'] == 'rainbow': pygame.draw.circle(screen, WHITE, (int(peg['x']), int(peg['y'])), 6, 2)
                elif peg['type'] == 'stat': pygame.draw.circle(screen, WHITE, (int(peg['x']), int(peg['y'])), 6, 2)
                elif peg['type'] == 'boss': pygame.draw.circle(screen, WHITE, (int(peg['x']), int(peg['y'])), int(PEG_RADIUS*1.5), 2)
                else: pygame.draw.circle(screen, WHITE, (int(peg['x']), int(peg['y'])), 7, 1)
                
        # Draw Drones
        for d in drones:
            dx, dy = int(d['x']), int(d['y'])
            # Body
            pygame.draw.rect(screen, GRAY, (dx - 20, dy - 5, 40, 10), border_radius=3)
            # Rotors
            pygame.draw.circle(screen, CYAN, (dx - 15, dy - 5), 8, 2)
            pygame.draw.circle(screen, CYAN, (dx + 15, dy - 5), 8, 2)
            # Net full of balls
            if d['balls']:
                pygame.draw.arc(screen, WHITE, (dx - 15, dy, 30, 20), math.pi, 0, 2)
                for i, b in enumerate(d['balls']):
                    bx = dx - 10 + (i % 5) * 5
                    by = dy + 5 + (i // 5) * 5
                    pygame.draw.circle(screen, b['color'], (bx, by), 3)

        if active_ability_mode == 'Thunder Cloud' and my < HEIGHT - 80:
            pygame.draw.circle(screen, WHITE, (mx, my), 35, 2)
            pygame.draw.circle(screen, WHITE, (mx - 25, my + 15), 25, 2)
            pygame.draw.circle(screen, WHITE, (mx + 25, my + 15), 25, 2)
        elif active_ability_mode == 'Fire Cursor' and my < HEIGHT - 80:
            pygame.draw.circle(screen, ORANGE, (mx, my), 30, 2)
            pygame.draw.circle(screen, RED, (mx, my), 4)
        elif active_ability_mode == 'Vacuum Cursor' and my < HEIGHT - 80:
            pygame.draw.circle(screen, CYAN, (mx, my), 200, 1)
            pygame.draw.circle(screen, WHITE, (mx, my), 10, 1)
            sec_left = f"{(vacuum_cursor_timer/FPS):.1f}s"
            screen.blit(font_med.render(sec_left, True, WHITE), (mx + 20, my - 20))
        elif active_ability_mode == 'Black Hole' and my < HEIGHT - 80:
            pygame.draw.circle(screen, PURPLE, (mx, my), 200, 2)
            pygame.draw.circle(screen, BLACK, (mx, my), 20)
            pygame.draw.circle(screen, PURPLE, (mx, my), 20, 2)
        elif active_ability_mode == 'Midas Touch' and my < HEIGHT - 80:
            pygame.draw.circle(screen, GOLD, (mx, my), 80, 2)
        elif active_ability_mode == 'Orbital Strike' and my < HEIGHT - 80:
            pygame.draw.rect(screen, RED, (mx - 45, 0, 90, HEIGHT), 2)
            pygame.draw.line(screen, RED, (mx, 0), (mx, HEIGHT), 1)
            
        if active_ability_mode == 'Fire Cursor':
            sec_left = f"{(fire_cursor_timer/FPS):.1f}s"
            screen.blit(font_med.render(sec_left, True, ORANGE), (mx + 20, my - 20))
            
        if not active_ability_mode:
            draw_cannon(mx, my)
        
        for p in particles: pygame.draw.circle(screen, p['color'], (int(p['x']), int(p['y'])), int(p['radius']))
        
        for b in balls: 
            pygame.draw.circle(screen, b['color'], (int(b['x']), int(b['y'])), b.get('radius', BALL_RADIUS))
            
            stack = b.get('revive_stack', [])
            for i, rev_type in enumerate(stack):
                color = CYAN if rev_type == 'top' else GREEN
                pulse = math.sin(pygame.time.get_ticks() / 100.0 + i) * 2
                ring_radius = int(b.get('radius', BALL_RADIUS) + 4 + (i * 5) + pulse)
                pygame.draw.circle(screen, color, (int(b['x']), int(b['y'])), ring_radius, 2)
            
        screen.blit(font_large.render(f"Cash: ${cash}", True, WHITE), (20, 10))
        screen.blit(font_med.render(f"PP: {prestige_points}", True, BRONZE), (20, 45))
        screen.blit(font_med.render(f"SP: {stat_points}", True, CYAN), (20, 75))
        
        manual_count = len([b for b in balls if b['is_manual'] and b['type'] == equipped_ball])
        max_am = ball_stats[equipped_ball]['max_balls']
        screen.blit(font_med.render(f"{equipped_ball} Ammo: {max(0, max_am - manual_count)} / {max_am}", True, WHITE), (20, 105))
        
        pygame.draw.rect(screen, TAN, (WIDTH - 120, 20, 100, 40), border_radius=5)
        screen.blit(font_med.render("MENU", True, BLACK), (WIDTH - 105, 28))

        eq_stat = ball_stats[equipped_ball]
        if eq_stat['auto_drop_lvl'] > 0:
            is_on = eq_stat.get('auto_enabled', True)
            pygame.draw.rect(screen, GREEN if is_on else RED, (WIDTH - 260, 20, 130, 40), border_radius=5)
            short_name = equipped_ball[:4].upper()
            screen.blit(font_small.render(f"{short_name} AUTO: {'ON' if is_on else 'OFF'}", True, BLACK), (WIDTH - 250, 32))

        if equipped_abilities:
            for i, a_name in enumerate(equipped_abilities):
                tokens = ability_inventory.get(a_name, 0)
                is_active = (active_ability_mode == a_name)
                
                ab_color = GOLD if is_active else (GREEN if tokens > 0 else RED)
                ab_rect = pygame.Rect(20, HEIGHT - 70 - (i * 60), 290, 50)
                pygame.draw.rect(screen, ab_color, ab_rect, border_radius=5)
                pygame.draw.rect(screen, WHITE if is_active else BLACK, ab_rect, 3, border_radius=5)
                
                status_text = "CANCEL" if is_active else "USE"
                screen.blit(font_med.render(f"{status_text} {a_name} (x{tokens})", True, BLACK), (ab_rect.x + 10, ab_rect.y + 15))

        if event_timer > 0:
            event_timer -= 1
            if "+3 PRESTIGE" in event_text_str: ev_txt = font_large.render(event_text_str, True, BRONZE)
            elif "+1 STAT POINT" in event_text_str: ev_txt = font_large.render(event_text_str, True, CYAN)
            else: ev_txt = font_large.render(event_text_str, True, get_rainbow_color())
            screen.blit(ev_txt, (WIDTH//2 - ev_txt.get_width()//2, 100))

        if board_clear_timer > 0:
            board_clear_timer -= 1
            clear_txt = font_huge.render("BOARD CLEARED!", True, CYAN)
            screen.blit(clear_txt, (WIDTH//2 - clear_txt.get_width()//2, HEIGHT//2 - clear_txt.get_height()//2))
            if board_clear_timer == 0:
                create_random_board() 
                balls.clear()
                particles.clear()
                lightnings.clear()
                clouds.clear()
                black_holes.clear()
                lasers.clear()
                drones.clear()

    elif state == "MENU":
        draw_main_menu()
    
    elif state == "ABILITIES_MENU":
        draw_abilities_menu()
        
    elif state == "CRATES_MENU":
        draw_crates_menu()

    elif state == "CRATE_REWARD":
        screen.fill(BLACK)
        screen.blit(font_huge.render("CRATE OPENED!", True, GOLD), (WIDTH//2 - 220, 100))
        
        cols = 5
        rows = math.ceil(len(crate_results_display) / cols)
        start_y = HEIGHT // 2 - (rows * 60)
        
        for i, res in enumerate(crate_results_display):
            r = i // cols
            c = i % cols
            x = WIDTH//2 - (cols * 100) + (c * 200) + 100
            y = start_y + (r * 150)
            
            rarity_color = RARITY_COLORS[res['rarity']]
            pygame.draw.rect(screen, DARK_GRAY, (x - 80, y, 160, 100), border_radius=10)
            pygame.draw.rect(screen, rarity_color, (x - 80, y, 160, 100), 3, border_radius=10)
            
            screen.blit(font_med.render(res['rarity'], True, rarity_color), (x - 60, y + 10))
            
            words = res['name'].split()
            if len(words) > 1:
                screen.blit(font_small.render(words[0], True, WHITE), (x - 60, y + 45))
                screen.blit(font_small.render(words[1], True, WHITE), (x - 60, y + 70))
            else:
                screen.blit(font_small.render(res['name'], True, WHITE), (x - 60, y + 55))
        
        btn_ok = pygame.Rect(WIDTH//2 - 75, HEIGHT - 150, 150, 50)
        pygame.draw.rect(screen, GREEN, btn_ok, border_radius=5)
        screen.blit(font_med.render("AWESOME", True, BLACK), (btn_ok.x + 15, btn_ok.y + 15))

    elif state == "OFFLINE_SCREEN":
        screen.fill(DARK_BG)
        
        anim_cash += (offline_rewards['cash'] - anim_cash) * 0.05 + 1
        anim_pp += (offline_rewards['pp'] - anim_pp) * 0.05 + 0.1
        anim_sp += (offline_rewards['sp'] - anim_sp) * 0.05 + 0.1
        
        if anim_cash > offline_rewards['cash']: anim_cash = offline_rewards['cash']
        if anim_pp > offline_rewards['pp']: anim_pp = offline_rewards['pp']
        if anim_sp > offline_rewards['sp']: anim_sp = offline_rewards['sp']
        
        pygame.draw.rect(screen, BLACK, (WIDTH//2 - 300, HEIGHT//2 - 250, 600, 500), border_radius=15)
        pygame.draw.rect(screen, CYAN, (WIDTH//2 - 300, HEIGHT//2 - 250, 600, 500), 4, border_radius=15)
        
        screen.blit(font_huge.render("WELCOME BACK!", True, GOLD), (WIDTH//2 - 260, HEIGHT//2 - 220))
        
        time_str = format_time(offline_rewards['time'])
        screen.blit(font_med.render(f"You were gone for {time_str}", True, GRAY), (WIDTH//2 - 180, HEIGHT//2 - 140))
        
        screen.blit(font_large.render(f"Cash Earned: ${int(anim_cash)}", True, GREEN), (WIDTH//2 - 200, HEIGHT//2 - 60))
        screen.blit(font_large.render(f"PP Earned: {int(anim_pp)}", True, BRONZE), (WIDTH//2 - 200, HEIGHT//2 - 10))
        screen.blit(font_large.render(f"SP Earned: {int(anim_sp)}", True, CYAN), (WIDTH//2 - 200, HEIGHT//2 + 40))
        
        btn_collect = pygame.Rect(WIDTH//2 - 100, HEIGHT - 150, 200, 60)
        
        is_done = (int(anim_cash) == offline_rewards['cash'] and int(anim_pp) == offline_rewards['pp'] and int(anim_sp) == offline_rewards['sp'])
        pygame.draw.rect(screen, GREEN if is_done else GRAY, btn_collect, border_radius=10)
        screen.blit(font_large.render("COLLECT", True, BLACK), (btn_collect.x + 25, btn_collect.y + 15))

    elif state == "CONFIRM_PRESTIGE":
        screen.blit(dim_overlay, (0, 0))
        pygame.draw.rect(screen, TAN, (WIDTH//2 - 250, HEIGHT//2 - 100, 500, 200), border_radius=10)
        pygame.draw.rect(screen, GOLD, (WIDTH//2 - 250, HEIGHT//2 - 100, 500, 200), 3, border_radius=10)
        
        screen.blit(font_med.render("Are you sure you want to Prestige?", True, BLACK), (WIDTH//2 - 210, HEIGHT//2 - 80))
        screen.blit(font_small.render("You will lose cash and ball upgrades,", True, DARK_GRAY), (WIDTH//2 - 170, HEIGHT//2 - 40))
        screen.blit(font_small.render("but you keep PP and get SP refunded.", True, DARK_GRAY), (WIDTH//2 - 160, HEIGHT//2 - 20))
        
        yes_rect = pygame.Rect(WIDTH//2 - 150, HEIGHT//2 + 20, 100, 50)
        pygame.draw.rect(screen, GREEN, yes_rect, border_radius=5)
        screen.blit(font_med.render("YES", True, BLACK), (yes_rect.x + 25, yes_rect.y + 15))
        
        no_rect = pygame.Rect(WIDTH//2 + 50, HEIGHT//2 + 20, 100, 50)
        pygame.draw.rect(screen, RED, no_rect, border_radius=5)
        screen.blit(font_med.render("NO", True, WHITE), (no_rect.x + 30, no_rect.y + 15))

    elif state == "PRESTIGE_TREE":
        draw_prestige_tree(mx, my)

    pygame.display.flip()
    clock.tick(FPS)

pygame.quit()
