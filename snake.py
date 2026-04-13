"""
╔══════════════════════════════════════════════════════════════╗
║                   SNAKE — NEON EDITION                      ║
║                 Desarrollado con pygame                     ║
╚══════════════════════════════════════════════════════════════╝

CÓMO EJECUTAR:
    1. Instala pygame:  pip install pygame
    2. Ejecuta:         python snake.py

CONTROLES:
    ← ↑ → ↓   o   W A S D   Mover la serpiente
    P                        Pausar / reanudar
    R                        Reiniciar partida
    ESC                      Salir

REGLAS:
    - Come la manzana para crecer y sumar puntos.
    - Cada 5 manzanas sube de nivel y la serpiente se vuelve más rápida.
    - Frutas especiales (doradas) aparecen por tiempo limitado y dan 50 pts.
    - Si chocas con la pared o con tu propio cuerpo, pierdes.
    - El rastro de luz se desvanece hacia atrás — efecto neon trail.
"""

import pygame
import sys
import random
import math
import colorsys

# ─────────────────────────────────────────────────────────────
# CONSTANTES
# ─────────────────────────────────────────────────────────────

CELL        = 28          # Tamaño de cada celda en píxeles
COLS        = 24          # Columnas del tablero
ROWS        = 20          # Filas del tablero
HUD_H       = 56          # Altura del HUD superior
SCREEN_W    = COLS * CELL
SCREEN_H    = ROWS * CELL + HUD_H
FPS         = 60

# Velocidad base: cada cuántos frames avanza la serpiente 1 celda
BASE_SPEED  = 10          # frames por movimiento en nivel 1
MIN_SPEED   = 4           # mínimo (nivel máximo)

# Puntos
PTS_APPLE   = 10
PTS_GOLDEN  = 50
PTS_LEVEL   = 5           # Manzanas necesarias para subir de nivel

# Duración de la fruta dorada (frames)
GOLDEN_LIFE = 300         # 5 segundos a 60 FPS

# ── Paleta neon oscura ────────────────────────────────────────
C_BG        = (6,   8,  18)    # Fondo casi negro
C_GRID      = (14,  18,  38)   # Líneas de cuadrícula muy tenues
C_TEXT      = (210, 220, 255)
C_TITLE     = (0,   240, 180)  # Verde-cian neon
C_HUD_BG    = (10,  12,  28)

# Colores de la serpiente (cabeza → cola)
C_HEAD      = (0,   255, 160)  # Verde neon brillante
C_BODY_A    = (0,   200, 120)
C_BODY_B    = (0,   140,  80)
C_TAIL      = (0,    60,  40)  # Verde oscuro apagado

# Colores de frutas
C_APPLE     = (255,  60,  80)  # Rojo neon
C_APPLE_G   = (255, 220,   0)  # Dorado

# Partículas de explosión al comer
C_PARTICLE  = [(255, 80, 80), (255, 160, 60), (255, 230, 80)]

# Dirección como vectores (dr, dc)
UP    = (-1,  0)
DOWN  = ( 1,  0)
LEFT  = ( 0, -1)
RIGHT = ( 0,  1)

# Opuestos (para evitar que la serpiente se gire 180°)
OPPOSITE = {UP: DOWN, DOWN: UP, LEFT: RIGHT, RIGHT: LEFT}


# ─────────────────────────────────────────────────────────────
# FUNCIONES DE DIBUJO CON EFECTO NEON
# ─────────────────────────────────────────────────────────────

def glow(surface, color, rect, radius=6, alpha=60):
    """
    Simula un halo luminoso (glow) dibujando círculos
    semitransparentes alrededor de un rectángulo.
    Se usa una superficie temporal con canal alpha.

    color  : color del brillo
    rect   : rectángulo central que brilla
    radius : grosor del halo
    alpha  : opacidad del halo (0=transparente, 255=sólido)
    """
    glow_surf = pygame.Surface(
        (rect.width + radius*4, rect.height + radius*4),
        pygame.SRCALPHA
    )
    for i in range(radius, 0, -1):
        a   = int(alpha * (i / radius) ** 2)
        col = (*color, a)
        pygame.draw.rect(
            glow_surf, col,
            pygame.Rect(radius*2 - i, radius*2 - i,
                        rect.width + i*2, rect.height + i*2),
            border_radius=i*2
        )
    surface.blit(glow_surf, (rect.x - radius*2, rect.y - radius*2))


def draw_rounded_cell(surface, rect, color, radius=6):
    """Dibuja una celda con bordes redondeados."""
    pygame.draw.rect(surface, color, rect, border_radius=radius)


def lerp_color(c1, c2, t):
    """
    Interpolación lineal entre dos colores.
    t=0 devuelve c1, t=1 devuelve c2.
    Usado para el degradado cabeza → cola.
    """
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))


# ─────────────────────────────────────────────────────────────
# CLASE: Particle
#
# Partículas de explosión que aparecen al comer una fruta.
# Vuelan en direcciones aleatorias y se desvanecen.
# ─────────────────────────────────────────────────────────────
class Particle:
    def __init__(self, x, y, color):
        angle = random.uniform(0, math.tau)
        speed = random.uniform(1.5, 5.0)
        self.x    = float(x)
        self.y    = float(y)
        self.dx   = math.cos(angle) * speed
        self.dy   = math.sin(angle) * speed
        self.life = random.randint(20, 45)
        self.max_life = self.life
        self.color = color
        self.size  = random.randint(3, 7)

    def update(self):
        self.x    += self.dx
        self.y    += self.dy
        self.dy   += 0.15   # Gravedad leve
        self.dx   *= 0.96   # Fricción
        self.life -= 1

    @property
    def alive(self):
        return self.life > 0

    def draw(self, surface):
        alpha = int(255 * self.life / self.max_life)
        size  = max(1, int(self.size * self.life / self.max_life))
        col   = (*self.color, alpha)
        surf  = pygame.Surface((size*2, size*2), pygame.SRCALPHA)
        pygame.draw.circle(surf, col, (size, size), size)
        surface.blit(surf, (int(self.x) - size, int(self.y) - size))


# ─────────────────────────────────────────────────────────────
# CLASE: Apple
#
# Fruta que la serpiente debe comer.
# Tiene una animación de pulso (scale up/down) y brilla.
# ─────────────────────────────────────────────────────────────
class Apple:
    def __init__(self, row, col, golden=False):
        self.row    = row
        self.col    = col
        self.golden = golden
        self.life   = GOLDEN_LIFE if golden else -1   # -1 = infinita
        self.frame  = 0

    def update(self):
        self.frame += 1
        if self.golden:
            self.life -= 1

    @property
    def expired(self):
        return self.golden and self.life <= 0

    def draw(self, surface):
        cx = self.col * CELL + CELL // 2
        cy = self.row * CELL + CELL // 2 + HUD_H

        # Pulso: radio oscila suavemente
        pulse  = math.sin(self.frame * 0.1) * 2
        radius = CELL // 2 - 4 + int(pulse)
        color  = C_APPLE_G if self.golden else C_APPLE

        # Halo neon
        rect = pygame.Rect(cx - radius, cy - radius, radius*2, radius*2)
        glow(surface, color, rect,
             radius=8 if self.golden else 5,
             alpha=80 if self.golden else 50)

        # Cuerpo de la fruta
        pygame.draw.circle(surface, color, (cx, cy), radius)

        # Brillo interior (especular)
        shine_x = cx - radius // 3
        shine_y = cy - radius // 3
        pygame.draw.circle(surface, (255, 255, 255),
                           (shine_x, shine_y), max(2, radius // 4))

        # Tallo
        pygame.draw.line(surface, (0, 180, 80),
                         (cx, cy - radius),
                         (cx + 4, cy - radius - 5), 2)

        # Si es dorada, muestra cuánto tiempo queda (barra circular)
        if self.golden:
            angle = (self.life / GOLDEN_LIFE) * 360
            pygame.draw.arc(surface,
                            (255, 255, 100),
                            pygame.Rect(cx - radius - 4, cy - radius - 4,
                                        (radius + 4) * 2, (radius + 4) * 2),
                            math.radians(90),
                            math.radians(90 + angle), 2)


# ─────────────────────────────────────────────────────────────
# CLASE: Snake
#
# La serpiente como lista de segmentos (fila, col).
# El índice 0 es la cabeza; el último es la cola.
# ─────────────────────────────────────────────────────────────
class Snake:
    def __init__(self):
        self.reset()

    def reset(self):
        # Empieza en el centro con 3 segmentos moviéndose a la derecha
        mid_r = ROWS // 2
        mid_c = COLS // 2
        self.body = [(mid_r, mid_c),
                     (mid_r, mid_c - 1),
                     (mid_r, mid_c - 2)]
        self.direction  = RIGHT
        self.next_dir   = RIGHT
        self.grew       = False   # Flag: si comió, no eliminar la cola

    def set_direction(self, d):
        """
        Cambia la dirección deseada.
        Impide girar 180° sobre sí misma.
        """
        if d != OPPOSITE.get(self.direction):
            self.next_dir = d

    def move(self):
        """
        Avanza la serpiente 1 celda:
          1. Aplica la dirección deseada.
          2. Calcula la nueva cabeza.
          3. Inserta la cabeza al inicio.
          4. Si no creció, elimina el último segmento.
        """
        self.direction = self.next_dir
        head_r, head_c = self.body[0]
        dr, dc = self.direction
        new_head = (head_r + dr, head_c + dc)
        self.body.insert(0, new_head)
        if self.grew:
            self.grew = False   # Ya creció: no eliminamos la cola
        else:
            self.body.pop()

    def grow(self):
        """Marca que en el próximo movimiento debe crecer."""
        self.grew = True

    def check_collision(self):
        """
        Detecta colisiones:
          - Con las paredes del tablero
          - Con su propio cuerpo (a partir del segmento 1)
        Retorna True si hay colisión (muerte).
        """
        head_r, head_c = self.body[0]
        # Pared
        if not (0 <= head_r < ROWS and 0 <= head_c < COLS):
            return True
        # Cuerpo propio (ignoramos la cabeza, índice 0)
        if (head_r, head_c) in self.body[1:]:
            return True
        return False

    def occupies(self, row, col):
        """Comprueba si la serpiente ocupa una celda dada."""
        return (row, col) in self.body

    def draw(self, surface, frame):
        """
        Dibuja cada segmento con un degradado cabeza → cola.
        La cabeza tiene brillo neon; la cola se apaga.
        También dibuja ojos en la cabeza.
        """
        n = len(self.body)

        for i, (r, c) in enumerate(reversed(self.body)):
            # t=0 → cola (oscuro),  t=1 → cabeza (brillante)
            t     = 1 - i / max(n - 1, 1)
            color = lerp_color(C_TAIL, C_HEAD, t)

            # Reducir tamaño ligeramente hacia la cola para efecto de perspectiva
            shrink = int((1 - t * 0.3) * 3)
            x = c * CELL + shrink
            y = r * CELL + shrink + HUD_H
            w = CELL - shrink * 2
            rect = pygame.Rect(x, y, w, w)

            draw_rounded_cell(surface, rect, color, radius=max(2, 8 - shrink))

            # Halo solo en cabeza y primer segmento
            if i >= n - 2:
                glow(surface, C_HEAD, rect, radius=4, alpha=40)

        # ── Ojos en la cabeza ──
        hr, hc = self.body[0]
        dr, dc = self.direction
        cx = hc * CELL + CELL // 2
        cy = hr * CELL + CELL // 2 + HUD_H

        # Calcular posición perpendicular a la dirección de movimiento
        perp = (dc, dr)   # Perpendicular al vector (dr, dc)
        for side in [-1, 1]:
            ex = cx + perp[0] * side * 5 + dc * 5
            ey = cy + perp[1] * side * 5 + dr * 5
            pygame.draw.circle(surface, (20, 20, 20), (int(ex), int(ey)), 4)
            pygame.draw.circle(surface, (200, 255, 200), (int(ex), int(ey)), 2)


# ─────────────────────────────────────────────────────────────
# CLASE: Grid (fondo animado)
#
# Cuadrícula con líneas que pulsan sutilmente según el nivel.
# ─────────────────────────────────────────────────────────────
class Grid:
    def draw(self, surface, frame, level):
        # Fondo
        surface.fill(C_BG)

        # Color de la cuadrícula varía ligeramente con el nivel
        hue   = (level * 30) % 360
        r, g, b = colorsys.hsv_to_rgb(hue / 360, 0.3, 0.1)
        grid_color = (int(r * 255), int(g * 255), int(b * 255))

        for c in range(COLS + 1):
            pygame.draw.line(surface, grid_color,
                             (c * CELL, HUD_H),
                             (c * CELL, SCREEN_H), 1)
        for r in range(ROWS + 1):
            pygame.draw.line(surface, grid_color,
                             (0, r * CELL + HUD_H),
                             (SCREEN_W, r * CELL + HUD_H), 1)

        # Borde del área de juego con glow
        border_rect = pygame.Rect(0, HUD_H, SCREEN_W, ROWS * CELL)
        pygame.draw.rect(surface, C_TITLE, border_rect, 2)


# ─────────────────────────────────────────────────────────────
# CLASE: ScorePopup
#
# Texto flotante que aparece al comer (+10, +50, etc.)
# Sube y se desvanece en ~1 segundo.
# ─────────────────────────────────────────────────────────────
class ScorePopup:
    def __init__(self, text, x, y, color):
        self.text  = text
        self.x     = float(x)
        self.y     = float(y)
        self.color = color
        self.life  = 55
        self.font  = pygame.font.SysFont("monospace", 18, bold=True)

    def update(self):
        self.y    -= 1.2
        self.life -= 1

    @property
    def alive(self):
        return self.life > 0

    def draw(self, surface):
        alpha = int(255 * self.life / 55)
        surf  = self.font.render(self.text, True, self.color)
        surf.set_alpha(alpha)
        surface.blit(surf, (int(self.x), int(self.y)))


# ─────────────────────────────────────────────────────────────
# CLASE: Game
# ─────────────────────────────────────────────────────────────
class Game:
    def __init__(self):
        self.font_xl = pygame.font.SysFont("monospace", 36, bold=True)
        self.font_lg = pygame.font.SysFont("monospace", 24, bold=True)
        self.font_md = pygame.font.SysFont("monospace", 16, bold=True)
        self.font_sm = pygame.font.SysFont("monospace", 13)
        self.hi_score = 0
        self.grid_bg  = Grid()
        self.reset()

    def reset(self):
        self.snake      = Snake()
        self.score      = 0
        self.level      = 1
        self.apples_eaten = 0   # Acumulado para subir de nivel
        self.frame      = 0
        self.move_timer = 0     # Contador de frames para el movimiento
        self.paused     = False
        self.game_over  = False
        self.particles  = []
        self.popups     = []

        # Fruta normal y dorada
        self.apple        = self._spawn_apple(golden=False)
        self.golden_apple = None
        self.golden_timer = 0   # Cuántos frames hasta que aparece la dorada

        self._schedule_golden()

    # ── Spawn de frutas ───────────────────────────────────────

    def _spawn_apple(self, golden=False):
        """
        Genera una fruta en una celda aleatoria libre
        (que no esté ocupada por la serpiente ni otra fruta).
        """
        occupied = set(self.snake.body)
        if self.apple:
            occupied.add((self.apple.row, self.apple.col))
        while True:
            r = random.randint(0, ROWS - 1)
            c = random.randint(0, COLS - 1)
            if (r, c) not in occupied:
                return Apple(r, c, golden=golden)

    def _schedule_golden(self):
        """Programa cuándo aparece la próxima fruta dorada."""
        self.golden_timer = random.randint(200, 400)

    # ── Actualización ─────────────────────────────────────────

    def update(self, keys):
        if self.paused or self.game_over:
            return

        self.frame += 1

        # ── Dirección (teclado) ──
        if keys[pygame.K_UP]    or keys[pygame.K_w]: self.snake.set_direction(UP)
        if keys[pygame.K_DOWN]  or keys[pygame.K_s]: self.snake.set_direction(DOWN)
        if keys[pygame.K_LEFT]  or keys[pygame.K_a]: self.snake.set_direction(LEFT)
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]: self.snake.set_direction(RIGHT)

        # ── Velocidad según nivel ──
        speed = max(MIN_SPEED, BASE_SPEED - (self.level - 1) * 1)

        # ── Mover serpiente cada `speed` frames ──
        self.move_timer += 1
        if self.move_timer >= speed:
            self.move_timer = 0
            self.snake.move()

            # ── Colisión con paredes o cuerpo ──
            if self.snake.check_collision():
                self._die()
                return

            # ── Comer fruta normal ──
            hr, hc = self.snake.body[0]
            if hr == self.apple.row and hc == self.apple.col:
                self._eat(self.apple, PTS_APPLE, C_APPLE)
                self.apple = self._spawn_apple(golden=False)

            # ── Comer fruta dorada ──
            if self.golden_apple and \
               hr == self.golden_apple.row and hc == self.golden_apple.col:
                self._eat(self.golden_apple, PTS_GOLDEN, C_APPLE_G)
                self.golden_apple = None
                self._schedule_golden()

        # ── Actualizar frutas ──
        self.apple.update()
        if self.golden_apple:
            self.golden_apple.update()
            if self.golden_apple.expired:
                self.golden_apple = None
                self._schedule_golden()

        # ── Temporizador fruta dorada ──
        if self.golden_apple is None:
            self.golden_timer -= 1
            if self.golden_timer <= 0:
                self.golden_apple = self._spawn_apple(golden=True)

        # ── Efectos ──
        for p in self.particles:
            p.update()
        self.particles = [p for p in self.particles if p.alive]

        for pop in self.popups:
            pop.update()
        self.popups = [pop for pop in self.popups if pop.alive]

    def _eat(self, apple, pts, color):
        """Lógica común al comer cualquier fruta."""
        self.snake.grow()
        self.score       += pts * self.level
        self.apples_eaten += 1

        # Subir de nivel cada PTS_LEVEL manzanas
        if self.apples_eaten % PTS_LEVEL == 0:
            self.level += 1

        # Partículas de explosión
        cx = apple.col * CELL + CELL // 2
        cy = apple.row * CELL + CELL // 2 + HUD_H
        for _ in range(20):
            self.particles.append(
                Particle(cx, cy, random.choice(C_PARTICLE))
            )

        # Popup de puntos
        self.popups.append(
            ScorePopup(f"+{pts * self.level}", cx - 20, cy - 10, color)
        )

        self.hi_score = max(self.hi_score, self.score)

    def _die(self):
        """La serpiente murió: explosión grande y game over."""
        for seg in self.snake.body:
            cx = seg[1] * CELL + CELL // 2
            cy = seg[0] * CELL + CELL // 2 + HUD_H
            for _ in range(5):
                self.particles.append(
                    Particle(cx, cy, random.choice([(0,255,160),(0,200,100)]))
                )
        self.game_over = True
        self.hi_score  = max(self.hi_score, self.score)

    # ── Renderizado ───────────────────────────────────────────

    def draw(self, surface):
        # Fondo y cuadrícula
        self.grid_bg.draw(surface, self.frame, self.level)

        # HUD
        self._draw_hud(surface)

        # Frutas
        self.apple.draw(surface)
        if self.golden_apple:
            self.golden_apple.draw(surface)

        # Serpiente
        self.snake.draw(surface, self.frame)

        # Efectos
        for p in self.particles:
            p.draw(surface)
        for pop in self.popups:
            pop.draw(surface)

        # Overlays
        if self.paused:
            self._draw_overlay(surface, "PAUSA", "(P) continuar")
        elif self.game_over:
            self._draw_overlay(surface, "GAME OVER",
                               f"Score: {self.score}   Hi: {self.hi_score}   (R) reiniciar")

    def _draw_hud(self, surface):
        """Barra superior con puntaje, nivel y mejor puntuación."""
        pygame.draw.rect(surface, C_HUD_BG, (0, 0, SCREEN_W, HUD_H))

        # Línea divisoria con glow
        pygame.draw.line(surface, C_TITLE, (0, HUD_H - 1), (SCREEN_W, HUD_H - 1), 2)

        # Título
        t = self.font_md.render("◈ SNAKE NEON ◈", True, C_TITLE)
        surface.blit(t, (SCREEN_W // 2 - t.get_width() // 2, 4))

        # Score
        sc = self.font_md.render(f"SCORE  {self.score:06d}", True, C_TEXT)
        surface.blit(sc, (10, 32))

        # Hi-score
        hi = self.font_md.render(f"BEST   {self.hi_score:06d}", True, (160, 160, 255))
        surface.blit(hi, (SCREEN_W // 2 - hi.get_width() // 2, 32))

        # Nivel con barra de progreso
        nxt    = PTS_LEVEL - (self.apples_eaten % PTS_LEVEL)
        lv_txt = self.font_md.render(f"NIV {self.level}  ({nxt} para subir)", True, C_TITLE)
        surface.blit(lv_txt, (SCREEN_W - lv_txt.get_width() - 10, 32))

        # Barra de progreso de nivel (pequeña, esquina derecha)
        progress = (self.apples_eaten % PTS_LEVEL) / PTS_LEVEL
        bar_w    = 120
        bar_x    = SCREEN_W - bar_w - 10
        bar_y    = 22
        pygame.draw.rect(surface, (30, 40, 80),
                         (bar_x, bar_y, bar_w, 6), border_radius=3)
        pygame.draw.rect(surface, C_TITLE,
                         (bar_x, bar_y, int(bar_w * progress), 6),
                         border_radius=3)

    def _draw_overlay(self, surface, title, subtitle):
        """Overlay semitransparente con título y subtítulo."""
        ov = pygame.Surface((SCREEN_W, SCREEN_H), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 180))
        surface.blit(ov, (0, 0))

        # Marco decorativo
        margin = 60
        box = pygame.Rect(margin, SCREEN_H//2 - 70,
                          SCREEN_W - margin*2, 130)
        pygame.draw.rect(surface, (15, 20, 50, 200), box, border_radius=12)
        pygame.draw.rect(surface, C_TITLE, box, 2, border_radius=12)

        t1 = self.font_xl.render(title, True, C_TITLE)
        surface.blit(t1, (SCREEN_W//2 - t1.get_width()//2, SCREEN_H//2 - 55))

        t2 = self.font_sm.render(subtitle, True, C_TEXT)
        surface.blit(t2, (SCREEN_W//2 - t2.get_width()//2, SCREEN_H//2 + 20))


# ─────────────────────────────────────────────────────────────
# FUNCIÓN PRINCIPAL
# ─────────────────────────────────────────────────────────────
def main():
    pygame.init()
    pygame.display.set_caption("Snake — Neon Edition")
    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
    clock  = pygame.time.Clock()

    game = Game()

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    pygame.quit()
                    sys.exit()
                if event.key == pygame.K_r:
                    game.reset()
                if event.key == pygame.K_p and not game.game_over:
                    game.paused = not game.paused

        keys = pygame.key.get_pressed()
        game.update(keys)
        game.draw(screen)
        pygame.display.flip()
        clock.tick(FPS)


if __name__ == "__main__":
    main()
