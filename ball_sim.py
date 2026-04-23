import pygame
import math
import random
import json
import os
import wave
import struct

# Initialize Pygame and Mixer for Audio
pygame.init()
pygame.mixer.init()

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

# --- EXPANDED SCREEN DIMENSIONS ---
WIDTH, HEIGHT = 1000, 800
PLAY_AREA_WIDTH = 750
UI_WIDTH = WIDTH - PLAY_AREA_WIDTH
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Bouncing Ring Idle Game - Expanded Space!")
clock = pygame.time.Clock()
font = pygame.font.SysFont(None, 24)
large_font = pygame.font.SysFont(None, 36)

# Colors
BLACK = (20, 20, 20)
WHITE = (255, 255, 255)
GRAY = (50, 50, 50)
LIGHT_GRAY = (200, 200, 200)

# Game Variables
SAVE_FILE = "save_data.json"
ring_center = (PLAY_AREA_WIDTH // 2, HEIGHT // 2)
ring_thickness = 10
cash = 0
balls = []
white_balls = []
particles = []
floating_texts = []

# Upgrades System
upgrades = {
    "max_balls": {"level": 1, "cost": 20, "val": 1},
    "hole_size": {"level": 1, "cost": 50, "val": 0.5},
    "ring_speed": {"level": 1, "cost": 30, "val": 0.02},
    "auto_spawn": {"level": 0, "cost": 100, "val": 0},
    "wb_lifetime": {"level": 0, "cost": 150, "val": 0}, # NEW UPGRADE (Adds 2 seconds per level)
    "extra_ring": {"level": 0, "cost": 5000, "val": 0} 
}

class Ring:
    def __init__(self, radius, speed_mult):
        self.radius = radius
        self.angle = 0.0
        self.speed_mult = speed_mult 

rings = []

def init_rings():
    """Builds the rings with larger gaps for the expanded window."""
    global rings
    rings = [Ring(350, 1.0)] # Base outer ring is now 350 radius
    for i in range(upgrades["extra_ring"]["level"]):
        new_radius = 350 - ((i + 1) * 85) # Gap increased to 85 pixels!
        speed_mult = -1.0 if i % 2 == 0 else 1.0 
        rings.append(Ring(new_radius, speed_mult))

# --- Saving & Loading ---
def load_game():
    global cash, upgrades
    if os.path.exists(SAVE_FILE):
        with open(SAVE_FILE, "r") as f:
            data = json.load(f)
            cash = data.get("cash", 0)
            for key, val in data.get("upgrades", {}).items():
                if key in upgrades: upgrades[key] = val

def save_game():
    with open(SAVE_FILE, "w") as f:
        json.dump({"cash": cash, "upgrades": upgrades}, f)

load_game()
init_rings()
max_balls = upgrades["max_balls"]["level"]
available_balls = max_balls

# Timers
white_ball_timer = 60 * 60 
auto_spawn_timer = 0

def get_smooth_color(value):
    color_stops = [
        (0, (50, 150, 255)), (100, (50, 255, 50)), (200, (255, 255, 50)),
        (300, (255, 150, 0)), (400, (255, 50, 50)), (500, (150, 50, 255))
    ]
    if value >= 500: return color_stops[-1][1]
    for i in range(len(color_stops) - 1):
        v1, c1 = color_stops[i]
        v2, c2 = color_stops[i+1]
        if v1 <= value < v2:
            t = (value - v1) / (v2 - v1)
            return (int(c1[0] + (c2[0] - c1[0]) * t), int(c1[1] + (c2[1] - c1[1]) * t), int(c1[2] + (c2[2] - c1[2]) * t))
    return color_stops[0][1]

# --- Visual Effect Classes ---
class FloatingText:
    def __init__(self, text, x, y, color):
        self.text, self.x, self.y, self.color, self.alpha, self.dy = text, x, y, color, 255, random.uniform(1.5, 3.0)
    def update(self):
        self.y -= self.dy
        self.alpha -= 4
    def draw(self, surface):
        text_surf = large_font.render(self.text, True, self.color)
        text_surf.set_alpha(max(0, self.alpha))
        surface.blit(text_surf, (self.x - text_surf.get_width()//2, self.y))

class Particle:
    def __init__(self, x, y, color, speed_mult=1.0):
        self.x, self.y, self.color = x, y, color
        self.vx, self.vy = random.uniform(-3, 3) * speed_mult, random.uniform(-3, 3) * speed_mult
        self.radius, self.life = random.uniform(3, 6), 255
    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.radius *= 0.95 
        self.life -= 10
    def draw(self, surface):
        if self.radius > 0.5: pygame.draw.circle(surface, self.color, (int(self.x), int(self.y)), int(self.radius))

# --- Game Entities ---
class Ball:
    def __init__(self, x, y, is_bonus=False):
        self.x, self.y = x, y
        self.radius = 16 
        self.vx, self.vy = random.uniform(-4, 4), random.uniform(-4, 4)
        self.value = 0
        self.is_bonus = is_bonus 

    def update(self):
        self.vy += 0.15 
        self.x += self.vx
        self.y += self.vy

        for ring in rings:
            dist_to_center = math.hypot(self.x - ring_center[0], self.y - ring_center[1])
            if abs(dist_to_center - ring.radius) < self.radius + ring_thickness / 2:
                ball_angle = math.atan2(self.y - ring_center[1], self.x - ring_center[0])
                diff = (ball_angle - ring.angle + math.pi) % (2 * math.pi) - math.pi
                
                if abs(diff) >= upgrades["hole_size"]["val"] / 2:
                    self.value += 1
                    bounce_sound.play()
                    
                    nx, ny = (self.x - ring_center[0]) / dist_to_center, (self.y - ring_center[1]) / dist_to_center
                    
                    if dist_to_center < ring.radius:
                        overlap = (dist_to_center + self.radius + ring_thickness/2) - ring.radius
                        self.x -= nx * overlap
                        self.y -= ny * overlap
                        dot_product = self.vx * nx + self.vy * ny
                        if dot_product > 0: 
                            self.vx -= 2.01 * dot_product * nx
                            self.vy -= 2.01 * dot_product * ny
                    else:
                        overlap = ring.radius - (dist_to_center - self.radius - ring_thickness/2)
                        self.x += nx * overlap
                        self.y += ny * overlap
                        dot_product = self.vx * nx + self.vy * ny
                        if dot_product < 0:
                            self.vx -= 2.01 * dot_product * nx
                            self.vy -= 2.01 * dot_product * ny

    def draw(self, surface):
        color = get_smooth_color(self.value)
        pygame.draw.circle(surface, color, (int(self.x), int(self.y)), int(self.radius))
        val_text = font.render(str(self.value), True, BLACK)
        surface.blit(val_text, (self.x - val_text.get_width()//2, self.y - val_text.get_height()//2))

class WhiteBall(Ball):
    def __init__(self, x, y):
        super().__init__(x, y)
        self.radius = 24 
        # Base 13 seconds + 2 extra seconds per upgrade level
        self.life_timer = (13 + upgrades["wb_lifetime"]["val"]) * 60 

    def update(self):
        self.vy += 0.15 
        self.x += self.vx
        self.y += self.vy
        self.life_timer -= 1

        for ring in rings:
            dist_to_center = math.hypot(self.x - ring_center[0], self.y - ring_center[1])
            if abs(dist_to_center - ring.radius) < self.radius + ring_thickness / 2:
                self.value += 1
                
                # Cap the maximum size at 40 so it doesn't break the physics between ring gaps
                self.radius = min(self.radius + 0.4, 40) 
                bounce_sound.play()
                
                nx, ny = (self.x - ring_center[0]) / dist_to_center, (self.y - ring_center[1]) / dist_to_center
                
                if dist_to_center < ring.radius:
                    overlap = (dist_to_center + self.radius + ring_thickness/2) - ring.radius
                    self.x -= nx * overlap
                    self.y -= ny * overlap
                    dot_product = self.vx * nx + self.vy * ny
                    if dot_product > 0:
                        self.vx -= 2.02 * dot_product * nx
                        self.vy -= 2.02 * dot_product * ny
                else:
                    overlap = ring.radius - (dist_to_center - self.radius - ring_thickness/2)
                    self.x += nx * overlap
                    self.y += ny * overlap
                    dot_product = self.vx * nx + self.vy * ny
                    if dot_product < 0:
                        self.vx -= 2.02 * dot_product * nx
                        self.vy -= 2.02 * dot_product * ny

    def draw(self, surface):
        pygame.draw.circle(surface, WHITE, (int(self.x), int(self.y)), int(self.radius))
        val_text = font.render(str(self.value), True, BLACK)
        surface.blit(val_text, (self.x - val_text.get_width()//2, self.y - val_text.get_height()//2))

def handle_all_collisions(all_physics_entities):
    for i in range(len(all_physics_entities)):
        for j in range(i + 1, len(all_physics_entities)):
            b1, b2 = all_physics_entities[i], all_physics_entities[j]
            dx, dy = b2.x - b1.x, b2.y - b1.y
            dist = math.hypot(dx, dy)
            min_dist = b1.radius + b2.radius
            
            if 0 < dist < min_dist:
                overlap = min_dist - dist
                nx, ny = dx / dist, dy / dist
                b1.x -= nx * (overlap / 2)
                b1.y -= ny * (overlap / 2)
                b2.x += nx * (overlap / 2)
                b2.y += ny * (overlap / 2)
                
                dvx, dvy = b1.vx - b2.vx, b1.vy - b2.vy
                dot_product = dvx * nx + dvy * ny
                if dot_product > 0:
                    b1.vx -= dot_product * nx
                    b1.vy -= dot_product * ny
                    b2.vx += dot_product * nx
                    b2.vy += dot_product * ny
                    bounce_sound.play()

# Re-spaced Upgrade Buttons for Larger UI
buttons = [
    {"key": "max_balls", "label": "+1 Max Ball", "rect": pygame.Rect(PLAY_AREA_WIDTH + 10, 80, UI_WIDTH - 20, 60)},
    {"key": "hole_size", "label": "+ Hole Size", "rect": pygame.Rect(PLAY_AREA_WIDTH + 10, 150, UI_WIDTH - 20, 60)},
    {"key": "ring_speed", "label": "+ Ring Speed", "rect": pygame.Rect(PLAY_AREA_WIDTH + 10, 220, UI_WIDTH - 20, 60)},
    {"key": "auto_spawn", "label": "+ Auto-Spawn", "rect": pygame.Rect(PLAY_AREA_WIDTH + 10, 290, UI_WIDTH - 20, 60)},
    {"key": "wb_lifetime", "label": "+ WB Life", "rect": pygame.Rect(PLAY_AREA_WIDTH + 10, 360, UI_WIDTH - 20, 60)},
    {"key": "extra_ring", "label": "+ Extra Ring", "rect": pygame.Rect(PLAY_AREA_WIDTH + 10, 430, UI_WIDTH - 20, 60)}
]

running = True
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            save_game()
            running = False
            
        elif event.type == pygame.MOUSEBUTTONDOWN:
            mx, my = event.pos
            if mx < PLAY_AREA_WIDTH:
                if available_balls > 0:
                    balls.append(Ball(mx, my))
                    available_balls -= 1
                    
            for btn in buttons:
                if btn["rect"].collidepoint((mx, my)):
                    key = btn["key"]
                    
                    if key == "extra_ring" and upgrades[key]["level"] >= 3:
                        continue 
                        
                    cost = upgrades[key]["cost"]
                    if cash >= cost:
                        cash -= cost
                        upgrades[key]["level"] += 1
                        
                        if key == "extra_ring":
                            upgrades[key]["cost"] = int(cost * 5) 
                            init_rings() 
                        else:
                            upgrades[key]["cost"] = int(cost * 1.5) 
                            
                        if key == "max_balls":
                            max_balls += 1
                            available_balls += 1
                        elif key == "hole_size": upgrades["hole_size"]["val"] += 0.1
                        elif key == "ring_speed": upgrades["ring_speed"]["val"] += 0.005
                        elif key == "wb_lifetime": upgrades["wb_lifetime"]["val"] += 2 # Adds 2 seconds

    # --- Game Logic ---
    for ring in rings:
        ring.angle = (ring.angle + upgrades["ring_speed"]["val"] * ring.speed_mult) % (2 * math.pi)

    if upgrades["auto_spawn"]["level"] > 0:
        auto_spawn_timer -= 1
        if auto_spawn_timer <= 0:
            if available_balls > 0:
                balls.append(Ball(ring_center[0], ring_center[1]))
                available_balls -= 1
            auto_spawn_timer = max(5, 60 - (upgrades["auto_spawn"]["level"] * 5))

    white_ball_timer -= 1
    if white_ball_timer <= 0:
        white_balls.append(WhiteBall(ring_center[0], ring_center[1]))
        white_ball_timer = 60 * 60 

    handle_all_collisions(balls + white_balls)

    white_balls_to_keep = []
    for wb in white_balls:
        wb.update()
        if wb.life_timer <= 0:
            for _ in range(50): particles.append(Particle(wb.x, wb.y, WHITE, speed_mult=3.0))
            for _ in range(wb.value): balls.append(Ball(wb.x, wb.y, is_bonus=True))
        else:
            white_balls_to_keep.append(wb)
    white_balls = white_balls_to_keep

    balls_to_keep = []
    for ball in balls:
        ball.update()
        if ball.x < -50 or ball.x > PLAY_AREA_WIDTH + 50 or ball.y > HEIGHT + 50 or ball.y < -50:
            cash += ball.value
            ball_color = get_smooth_color(ball.value)
            exit_x, exit_y = max(20, min(ball.x, PLAY_AREA_WIDTH - 20)), max(20, min(ball.y, HEIGHT - 20))
            floating_texts.append(FloatingText(f"+${ball.value}", exit_x, exit_y, (50, 255, 50)))
            for _ in range(15): particles.append(Particle(exit_x, exit_y, ball_color))
            if not ball.is_bonus: available_balls += 1
        else:
            balls_to_keep.append(ball)
    balls = balls_to_keep

    for p in particles[:]:
        p.update()
        if p.life <= 0: particles.remove(p)
    for ft in floating_texts[:]:
        ft.update()
        if ft.alpha <= 0: floating_texts.remove(ft)

    # --- Rendering ---
    screen.fill(BLACK)

    for ring in rings:
        start_arc = -ring.angle + upgrades["hole_size"]["val"] / 2
        end_arc = -ring.angle - upgrades["hole_size"]["val"] / 2 + 2 * math.pi
        rect = pygame.Rect(ring_center[0] - ring.radius, ring_center[1] - ring.radius, ring.radius * 2, ring.radius * 2)
        pygame.draw.arc(screen, WHITE, rect, start_arc, end_arc, ring_thickness)

    for ball in balls: ball.draw(screen)
    for wb in white_balls: wb.draw(screen)
    for p in particles: p.draw(screen)
    for ft in floating_texts: ft.draw(screen)

    # --- UI Drawing ---
    pygame.draw.rect(screen, GRAY, (PLAY_AREA_WIDTH, 0, UI_WIDTH, HEIGHT))
    pygame.draw.line(screen, WHITE, (PLAY_AREA_WIDTH, 0), (PLAY_AREA_WIDTH, HEIGHT), 2)

    balls_text = large_font.render(f"Balls: {available_balls} / {max_balls}", True, WHITE)
    screen.blit(balls_text, (20, 20))
    cash_text = large_font.render(f"Cash: ${cash}", True, (50, 255, 50))
    screen.blit(cash_text, (PLAY_AREA_WIDTH + 10, 20))
    
    for btn in buttons:
        key = btn["key"]
        
        if key == "extra_ring" and upgrades[key]["level"] >= 3:
            lbl_text = font.render(btn["label"] + " (MAX)", True, BLACK)
            cost_text = font.render("Cost: N/A", True, BLACK)
            color = (100, 100, 100)
        else:
            cost = upgrades[key]["cost"]
            color = LIGHT_GRAY if cash >= cost else (100, 100, 100)
            lbl_text = font.render(btn["label"], True, BLACK)
            cost_text = font.render(f"Cost: ${cost}", True, BLACK)
            
        pygame.draw.rect(screen, color, btn["rect"], border_radius=5)
        screen.blit(lbl_text, (btn["rect"].x + 10, btn["rect"].y + 10))
        screen.blit(cost_text, (btn["rect"].x + 10, btn["rect"].y + 35))

    pygame.display.flip()
    clock.tick(60)

pygame.quit()
