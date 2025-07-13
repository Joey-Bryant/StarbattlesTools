# --- Silence Pygame messages and warnings ---
import os
import warnings

os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "1"
warnings.filterwarnings("ignore", category=RuntimeWarning, message="Your system is avx2 capable but pygame was not built with support for it.*")
warnings.filterwarnings("ignore", category=UserWarning, message="pkg_resources is deprecated as an API.*")
# --- End of silencing code ---

import pygame
import requests
import re
import sys
import math
import hashlib
from collections import deque

# --- UI Constants ---
GRID_AREA_WIDTH = 600; GRID_AREA_HEIGHT = 600
PANEL_WIDTH = 250; WINDOW_WIDTH = GRID_AREA_WIDTH + PANEL_WIDTH; WINDOW_HEIGHT = GRID_AREA_HEIGHT
GUTTER = 5; BORDER_NORMAL = 1; BORDER_THICK = 4

# --- Colors ---
COLOR_WHITE = (255, 255, 255); COLOR_BLACK = (0, 0, 0); COLOR_GRID_LINES = (200, 200, 200)
COLOR_STAR = (255, 200, 0); COLOR_X = (40, 40, 40); COLOR_DOT = (150, 150, 150)
COLOR_PANEL = (50, 50, 60); COLOR_BUTTON = (80, 80, 90); COLOR_BUTTON_HOVER = (110, 110, 120)
COLOR_BUTTON_TEXT = (220, 220, 220); COLOR_CORRECT = (0, 200, 0); COLOR_INCORRECT = (200, 0, 0)
COLOR_SELECTED = (100, 180, 255); COLOR_STAR_NUM = (200, 0, 0)
COLOR_DISABLED_BUTTON = (60, 60, 70); COLOR_DISABLED_TEXT = (100, 100, 110)

DIFFICULTY_COLORS = {
    'easy':   {'base': (70, 160, 70),  'hover': (90, 190, 90)},
    'medium': {'base': (180, 140, 50), 'hover': (210, 170, 70)},
    'hard':   {'base': (180, 70, 70),  'hover': (210, 90, 90)}
}

UNIFIED_COLORS = [
    ("Bright Red",(255,204,204),"\033[91m"),("Bright Green",(204,255,204),"\033[92m"),
    ("Bright Yellow",(255,255,204),"\033[93m"),("Bright Blue",(204,229,255),"\033[94m"),
    ("Bright Magenta",(255,204,255),"\033[95m"),("Bright Cyan",(204,255,255),"\033[96m"),
    ("Light Orange",(255,229,204),"\033[33m"),("Light Purple",(229,204,255),"\033[35m"),
    ("Light Gray",(224,224,224),"\033[37m"),("Mint",(210,240,210),"\033[32m"),
    ("Peach",(255,218,185),"\033[91m"),("Sky Blue",(173,216,230),"\033[34m"),
]

STATE_EMPTY = 0; STATE_STAR = 1; STATE_SECONDARY_MARK = 2
SBN_ALPHABET = {c: i for i, c in enumerate('0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz-_')}
SBN_CODE_TO_DIM_MAP = {'99': 9, 'AA': 10, 'BB': 12, 'CC': 14, 'DD': 16, 'EE': 17, 'FF': 18, 'GG': 20, 'HH': 21, 'LL': 25}
# NEW: Base64 alphabet for terminal display to ensure single-character alignment
BASE64_DISPLAY_ALPHABET = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz-_'

PUZZLE_DEFINITIONS = [
    {'dim': 5,  'stars': 1, 'difficulty': 'easy'},   # 0
    {'dim': 6,  'stars': 1, 'difficulty': 'easy'},   # 1
    {'dim': 6,  'stars': 1, 'difficulty': 'medium'}, # 2
    {'dim': 8,  'stars': 2, 'difficulty': 'medium'}, # 3
    {'dim': 8,  'stars': 2, 'difficulty': 'hard'},   # 4
    {'dim': 10, 'stars': 2, 'difficulty': 'medium'}, # 5
    {'dim': 10, 'stars': 2, 'difficulty': 'hard'},   # 6
    {'dim': 14, 'stars': 3, 'difficulty': 'medium'}, # 7
    {'dim': 14, 'stars': 3, 'difficulty': 'hard'},   # 8
    {'dim': 17, 'stars': 4, 'difficulty': 'hard'},   # 9
    {'dim': 21, 'stars': 5, 'difficulty': 'hard'},   # 10
    {'dim': 25, 'stars': 6, 'difficulty': 'hard'}    # 11
]
WEBSITE_SIZE_IDS = list(range(12))

def get_puzzle_from_website(size_selection):
    url = "REDACTED"
    website_size_id = WEBSITE_SIZE_IDS[size_selection]
    if website_size_id != 0: url += f"?size={website_size_id}"
    
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    print(f"Fetching puzzle data from {url}...")
    try:
        response = requests.get(url, headers=headers, timeout=10); response.raise_for_status()
        task_match = re.search(r"var task = '([^']+)';", response.text)
        hash_match = re.search(r"hashedSolution: '([^']+)'", response.text)
        if task_match and hash_match:
            print("Successfully extracted puzzle and solution hash.")
            return {'task': task_match.group(1), 'solution_hash': hash_match.group(1)}
        print("Error: Could not find required puzzle data."); return None
    except requests.RequestException as e:
        print(f"Error: Could not fetch puzzle data. {e}"); return None

def decode_sbn(sbn_string):
    print(f"Decoding SBN: {sbn_string}")
    try:
        size_code = sbn_string[0:2]
        dim = SBN_CODE_TO_DIM_MAP.get(size_code)
        if not dim: print(f"Error: Unknown SBN size code '{size_code}'"); return None
        
        stars = int(sbn_string[2]); region_data = sbn_string[4:]
        bitfield = "".join(bin(SBN_ALPHABET[char])[2:].zfill(6) for char in region_data)
        
        num_borders = dim * (dim - 1)
        vertical_bits = bitfield[:num_borders]; horizontal_bits = bitfield[num_borders : num_borders * 2]
        
        region_grid = [[0] * dim for _ in range(dim)]; region_id = 1
        for r_start in range(dim):
            for c_start in range(dim):
                if region_grid[r_start][c_start] == 0:
                    q = deque([(r_start, c_start)]); region_grid[r_start][c_start] = region_id
                    while q:
                        r, c = q.popleft()
                        if r > 0 and region_grid[r-1][c] == 0 and horizontal_bits[c*(dim-1) + (r-1)] == '0':
                            region_grid[r-1][c] = region_id; q.append((r-1, c))
                        if r < dim - 1 and region_grid[r+1][c] == 0 and horizontal_bits[c*(dim-1) + r] == '0':
                            region_grid[r+1][c] = region_id; q.append((r+1, c))
                        if c > 0 and region_grid[r][c-1] == 0 and vertical_bits[r*(dim-1) + (c-1)] == '0':
                            region_grid[r][c-1] = region_id; q.append((r, c-1))
                        if c < dim - 1 and region_grid[r][c+1] == 0 and vertical_bits[r*(dim-1) + c] == '0':
                            region_grid[r][c+1] = region_id; q.append((r, c+1))
                    region_id += 1
        
        task_string = ",".join(str(cell) for row in region_grid for cell in row)
        print(f"SBN decoded successfully to a {dim}x{dim} grid with {stars} stars.")
        return {'task': task_string, 'solution_hash': None, 'stars': stars}

    except (KeyError, IndexError, ValueError) as e:
        print(f"Error decoding SBN: Invalid format. {e}"); return None

def reset_game_state(puzzle_data):
    if not puzzle_data or 'task' not in puzzle_data: return None, None, None, None, None, None
    region_grid, dimension = parse_and_validate_grid(puzzle_data['task'])
    if region_grid:
        display_grid_as_symbols(region_grid)
        player_grid = [[STATE_EMPTY] * dimension for _ in range(dimension)]
        cell_size = GRID_AREA_WIDTH / dimension
        stars = puzzle_data.get('stars', 2)
        return region_grid, puzzle_data, player_grid, dimension, cell_size, stars
    return None, None, None, None, None, None

def parse_and_validate_grid(task_string):
    if not task_string: return None, None
    try:
        numbers = [int(n) for n in task_string.split(',')]; total_cells = len(numbers)
        if total_cells == 0: return None, None
        dimension = int(math.sqrt(total_cells))
        if dimension * dimension != total_cells:
            print(f"Error: Data length ({total_cells}) is not a perfect square."); return None, None
        grid = [numbers[i*dimension:(i+1)*dimension] for i in range(dimension)]
        print(f"Successfully parsed a {dimension}x{dimension} grid.")
        return grid, dimension
    except (ValueError, TypeError): return None, None

def display_grid_as_symbols(grid):
    """Displays the grid using a single, colored Base64 character per region."""
    if not grid: return
    RESET = "\033[0m"; print("\n--- Terminal Symbol Display ---")
    for row in grid:
        colored_chars = []
        for cell_num in row:
            # Use the region number to look up the Base64 symbol
            symbol = BASE64_DISPLAY_ALPHABET[cell_num - 1] if 0 < cell_num <= len(BASE64_DISPLAY_ALPHABET) else '?'
            color_ansi = UNIFIED_COLORS[(cell_num - 1) % len(UNIFIED_COLORS)][2]
            colored_chars.append(f"{color_ansi}{symbol}{RESET}")
        print(" ".join(colored_chars))
    print("-----------------------------\n")

def calculate_star_points(center_x, center_y, outer_radius, inner_radius):
    points = [];
    for i in range(10):
        angle = math.pi / 5 * i - math.pi / 2; radius = outer_radius if i % 2 == 0 else inner_radius
        points.append((center_x + radius * math.cos(angle), center_y + radius * math.sin(angle)))
    return points

def check_solution(player_grid, puzzle_data):
    if not puzzle_data or 'solution_hash' not in puzzle_data or not puzzle_data['solution_hash']: return False
    yn_string = "".join(['y' if cell == STATE_STAR else 'n' for row in player_grid for cell in row])
    string_to_hash = puzzle_data['task'] + yn_string
    calculated_hash = hashlib.md5(string_to_hash.encode('utf-8')).hexdigest()
    is_correct = calculated_hash == puzzle_data['solution_hash']
    print(f"Calculated Hash: {calculated_hash}\nExpected Hash:   {puzzle_data['solution_hash']}")
    if is_correct: print("\033[92m--> Solution is CORRECT!\033[0m")
    else: print("\033[91m--> Solution is INCORRECT.\033[0m")
    return is_correct

def draw_background_colors(screen, region_grid, cell_size):
    dim = len(region_grid)
    for r in range(dim):
        for c in range(dim):
            rect = pygame.Rect(c * cell_size, r * cell_size, cell_size, cell_size)
            pygame.draw.rect(screen, UNIFIED_COLORS[(region_grid[r][c] - 1) % len(UNIFIED_COLORS)][1], rect)

def draw_grid_lines(screen, region_grid, cell_size):
    dim = len(region_grid)
    for i in range(dim + 1):
        pygame.draw.line(screen, COLOR_GRID_LINES, (i * cell_size, 0), (i * cell_size, GRID_AREA_HEIGHT), BORDER_NORMAL)
        pygame.draw.line(screen, COLOR_GRID_LINES, (0, i * cell_size), (GRID_AREA_WIDTH, i * cell_size), BORDER_NORMAL)
    for r in range(dim):
        for c in range(dim):
            if c < dim - 1 and region_grid[r][c] != region_grid[r][c+1]:
                pygame.draw.line(screen, COLOR_BLACK, ((c + 1) * cell_size, r * cell_size), ((c + 1) * cell_size, (r + 1) * cell_size), BORDER_THICK)
            if r < dim - 1 and region_grid[r][c] != region_grid[r+1][c]:
                pygame.draw.line(screen, COLOR_BLACK, (c * cell_size, (r + 1) * cell_size), ((c + 1) * cell_size, (r + 1) * cell_size), BORDER_THICK)

def draw_player_marks(screen, player_grid, mark_is_x, cell_size):
    dim = len(player_grid)
    for r in range(dim):
        for c in range(dim):
            cell_state = player_grid[r][c]; center_x = c * cell_size + cell_size // 2; center_y = r * cell_size + cell_size // 2
            if cell_state == STATE_STAR:
                outer_rad = cell_size / 2 - GUTTER * 1.5; inner_rad = outer_rad / 2
                pygame.draw.polygon(screen, COLOR_STAR, calculate_star_points(center_x, center_y, outer_rad, inner_rad))
            elif cell_state == STATE_SECONDARY_MARK:
                if mark_is_x:
                    margin = GUTTER * 2.5; line_width = max(1, int(cell_size / 15))
                    pygame.draw.line(screen, COLOR_X, (c * cell_size + margin, r * cell_size + margin), ((c+1) * cell_size - margin, (r+1) * cell_size - margin), line_width)
                    pygame.draw.line(screen, COLOR_X, ((c+1) * cell_size - margin, r * cell_size + margin), (c * cell_size + margin, (r+1) * cell_size - margin), line_width)
                else:
                    pygame.draw.circle(screen, COLOR_DOT, (center_x, center_y), cell_size / 6)

def draw_star_indicator(screen, rect, count, font):
    star_radius = 12
    center_x = rect.right - star_radius + 5; center_y = rect.top + star_radius - 8
    star_points = calculate_star_points(center_x, center_y, star_radius, star_radius/2)
    pygame.draw.polygon(screen, COLOR_STAR, star_points)
    num_surf = font.render(str(count), True, COLOR_STAR_NUM)
    screen.blit(num_surf, num_surf.get_rect(center=(center_x, center_y + 1)))

def draw_control_panel(screen, font, small_font, tiny_font, buttons, size_buttons, current_size_selection, mark_is_x, solution_status, puzzle_data_exists):
    pygame.draw.rect(screen, COLOR_PANEL, (GRID_AREA_WIDTH, 0, PANEL_WIDTH, WINDOW_HEIGHT))
    mouse_pos = pygame.mouse.get_pos()
    buttons['toggle']['text'] = "Mode: Xs" if mark_is_x else "Mode: Dots"
    for name, b in buttons.items():
        is_disabled = (name == 'check' and not puzzle_data_exists)
        color = COLOR_DISABLED_BUTTON if is_disabled else (COLOR_BUTTON_HOVER if b['rect'].collidepoint(mouse_pos) else COLOR_BUTTON)
        pygame.draw.rect(screen, color, b['rect'], border_radius=8)
        text_color = COLOR_DISABLED_TEXT if is_disabled else COLOR_BUTTON_TEXT
        text_surf = font.render(b['text'], True, text_color)
        screen.blit(text_surf, text_surf.get_rect(center=b['rect'].center))

    title_surf = font.render("Board Size", True, COLOR_BUTTON_TEXT)
    screen.blit(title_surf, title_surf.get_rect(center=(GRID_AREA_WIDTH + PANEL_WIDTH // 2, buttons['toggle']['rect'].bottom + 40)))
    
    for size_id, b in size_buttons.items():
        puzzle_def = PUZZLE_DEFINITIONS[size_id]
        diff_colors = DIFFICULTY_COLORS[puzzle_def['difficulty']]
        color = diff_colors['hover'] if b['rect'].collidepoint(mouse_pos) else diff_colors['base']
        pygame.draw.circle(screen, color, b['rect'].center, b['radius'])
        if size_id == current_size_selection: pygame.draw.circle(screen, COLOR_SELECTED, b['rect'].center, b['radius'], 3)
        
        num_surf = small_font.render(str(puzzle_def['dim']), True, COLOR_BUTTON_TEXT)
        screen.blit(num_surf, num_surf.get_rect(center=b['rect'].center))
        draw_star_indicator(screen, b['rect'], puzzle_def['stars'], tiny_font)

    if solution_status:
        color = COLOR_CORRECT if solution_status == "Correct!" else COLOR_INCORRECT
        status_surf = font.render(solution_status, True, color)
        status_rect = status_surf.get_rect(center=(GRID_AREA_WIDTH + PANEL_WIDTH // 2, buttons['check']['rect'].top - 30))
        screen.blit(status_surf, status_rect)

def draw_feedback_overlay(screen, color, alpha):
    if alpha > 0:
        overlay = pygame.Surface((GRID_AREA_WIDTH, GRID_AREA_HEIGHT), pygame.SRCALPHA)
        overlay.fill((*color, alpha)); screen.blit(overlay, (0, 0))

def draw_sbn_input_box(screen, font, text):
    box_rect = pygame.Rect(WINDOW_WIDTH // 2 - 200, WINDOW_HEIGHT // 2 - 50, 400, 100)
    pygame.draw.rect(screen, COLOR_PANEL, box_rect, border_radius=10)
    pygame.draw.rect(screen, COLOR_SELECTED, box_rect, 2, 10)
    prompt_surf = font.render("Enter SBN:", True, COLOR_BUTTON_TEXT)
    screen.blit(prompt_surf, (box_rect.x + 10, box_rect.y + 10))
    text_surf = font.render(text, True, COLOR_BUTTON_TEXT)
    screen.blit(text_surf, (box_rect.x + 10, box_rect.y + 50))
    pygame.display.flip()

def get_sbn_input(screen, font):
    sbn_text = ""; input_active = True
    while input_active:
        for event in pygame.event.get():
            if event.type == pygame.QUIT: return None
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_RETURN: return sbn_text
                elif event.key == pygame.K_ESCAPE: return None
                elif event.key == pygame.K_BACKSPACE: sbn_text = sbn_text[:-1]
                else: sbn_text += event.unicode
        draw_sbn_input_box(screen, font, sbn_text)
    return None

def main():
    pygame.init()
    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    pygame.display.set_caption("Star Battle Playground")
    clock = pygame.time.Clock(); font = pygame.font.Font(None, 32)
    small_font = pygame.font.Font(None, 24); tiny_font = pygame.font.Font(None, 18)

    current_size_selection = 5
    puzzle_data = get_puzzle_from_website(current_size_selection)
    (region_grid, _, player_grid, current_grid_dim,
     cell_size, stars_per_region) = reset_game_state(puzzle_data)
    if not region_grid: sys.exit(1)
    
    b_width, b_height, b_margin = 200, 50, 20
    buttons = {
        'new': {'rect': pygame.Rect(GRID_AREA_WIDTH+(PANEL_WIDTH-b_width)//2, b_margin, b_width, b_height), 'text': 'New Puzzle'},
        'sbn': {'rect': pygame.Rect(GRID_AREA_WIDTH+(PANEL_WIDTH-b_width)//2, b_margin*2+b_height, b_width, b_height), 'text': 'Load SBN'},
        'clear': {'rect': pygame.Rect(GRID_AREA_WIDTH+(PANEL_WIDTH-b_width)//2, b_margin*3+b_height*2, b_width, b_height), 'text': 'Clear Board'},
        'toggle': {'rect': pygame.Rect(GRID_AREA_WIDTH+(PANEL_WIDTH-b_width)//2, b_margin*4+b_height*3, b_width, b_height), 'text': ''},
        'check': {'rect': pygame.Rect(GRID_AREA_WIDTH+(PANEL_WIDTH-b_width)//2, WINDOW_HEIGHT-b_margin-b_height, b_width, b_height), 'text': 'Check Solution'}
    }
    size_buttons = {}
    s_radius, s_cols, s_padding = 22, 4, (PANEL_WIDTH - (4 * 22 * 2)) // 5
    for i in range(12):
        row, col = divmod(i, s_cols)
        y = buttons['toggle']['rect'].bottom + 80 + row * (s_radius * 2 + s_padding)
        x = GRID_AREA_WIDTH + s_padding + col * (s_radius * 2 + s_padding) + s_radius
        size_buttons[i] = {'rect': pygame.Rect(x-s_radius, y-s_radius, s_radius*2, s_radius*2), 'radius': s_radius}
    
    mark_is_x, solution_status = True, None
    is_left_down, is_dragging, click_cell = False, False, None
    feedback_overlay_alpha, feedback_overlay_color = 0, COLOR_CORRECT; FADE_SPEED = 4

    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT: running = False
            def reset_feedback(): nonlocal solution_status, feedback_overlay_alpha; solution_status, feedback_overlay_alpha = None, 0
            
            if event.type == pygame.MOUSEBUTTONDOWN:
                pos = event.pos
                if event.button == 1: # Left Click
                    clicked_on_button = False
                    for b_name, b_data in {**buttons, **size_buttons}.items():
                        is_disabled = (b_name == 'check' and (not puzzle_data or not puzzle_data.get('solution_hash')))
                        if b_data['rect'].collidepoint(pos) and not is_disabled:
                            clicked_on_button = True
                            if b_name == 'new':
                                new_puzzle_data = get_puzzle_from_website(current_size_selection)
                                if new_puzzle_data:
                                    puzzle_data = new_puzzle_data
                                    new_state = reset_game_state(puzzle_data)
                                    if new_state[0]: (region_grid, _, player_grid, current_grid_dim, cell_size, stars_per_region) = new_state
                                reset_feedback()
                            elif b_name == 'clear':
                                player_grid = [[STATE_EMPTY] * current_grid_dim for _ in range(current_grid_dim)]; reset_feedback()
                            elif b_name == 'toggle':
                                mark_is_x = not mark_is_x
                            elif b_name == 'sbn':
                                sbn_string = get_sbn_input(screen, font)
                                if sbn_string:
                                    new_puzzle_data = decode_sbn(sbn_string)
                                    if new_puzzle_data:
                                        puzzle_data = new_puzzle_data
                                        new_state = reset_game_state(puzzle_data)
                                        if new_state and new_state[0]:
                                            (region_grid, _, player_grid, current_grid_dim, cell_size, stars_per_region) = new_state
                                            current_size_selection = -1
                                            reset_feedback()
                            elif b_name == 'check':
                                is_correct = check_solution(player_grid, puzzle_data); solution_status = "Correct!" if is_correct else "Incorrect!"
                                feedback_overlay_color = COLOR_CORRECT if is_correct else COLOR_INCORRECT; feedback_overlay_alpha = 128
                            elif isinstance(b_name, int):
                                current_size_selection = b_name
                                new_puzzle_data = get_puzzle_from_website(current_size_selection)
                                if new_puzzle_data:
                                    puzzle_data = new_puzzle_data
                                    new_state = reset_game_state(puzzle_data)
                                    if new_state and new_state[0]: (region_grid, _, player_grid, current_grid_dim, cell_size, stars_per_region) = new_state
                                    reset_feedback()
                            break
                    if not clicked_on_button and pos[0] < GRID_AREA_WIDTH:
                        col, row = int(pos[0] // cell_size), int(pos[1] // cell_size)
                        if 0 <= col < current_grid_dim: is_left_down, is_dragging, click_cell = True, False, (row, col)
                
                elif event.button == 3 and pos[0] < GRID_AREA_WIDTH:
                    col, row = int(pos[0] // cell_size), int(pos[1] // cell_size)
                    if 0 <= col < current_grid_dim: player_grid[row][col] = STATE_EMPTY if player_grid[row][col] == STATE_STAR else STATE_STAR; reset_feedback()
            
            elif event.type == pygame.MOUSEMOTION:
                if is_left_down:
                    is_dragging = True; col, row = int(event.pos[0] // cell_size), int(event.pos[1] // cell_size)
                    if 0 <= col < current_grid_dim and 0 <= row < current_grid_dim:
                        if player_grid[row][col] != STATE_SECONDARY_MARK: player_grid[row][col] = STATE_SECONDARY_MARK; reset_feedback()
            
            elif event.type == pygame.MOUSEBUTTONUP:
                if event.button == 1:
                    if not is_dragging and click_cell:
                        row, col = click_cell; state = player_grid[row][col]
                        if state == STATE_EMPTY: player_grid[row][col] = STATE_SECONDARY_MARK
                        elif state == STATE_SECONDARY_MARK: player_grid[row][col] = STATE_STAR
                        elif state == STATE_STAR: player_grid[row][col] = STATE_EMPTY
                        reset_feedback()
                    is_left_down, is_dragging, click_cell = False, False, None
        
        screen.fill(COLOR_PANEL)
        if region_grid:
            draw_background_colors(screen, region_grid, cell_size)
            draw_player_marks(screen, player_grid, mark_is_x, cell_size)
            draw_grid_lines(screen, region_grid, cell_size)
            draw_feedback_overlay(screen, feedback_overlay_color, feedback_overlay_alpha)
        if feedback_overlay_alpha > 0: feedback_overlay_alpha = max(0, feedback_overlay_alpha - FADE_SPEED)
        draw_control_panel(screen, font, small_font, tiny_font, buttons, size_buttons, current_size_selection, mark_is_x, solution_status, bool(puzzle_data and puzzle_data.get('solution_hash')))
        pygame.display.set_caption(f"Star Battle ({stars_per_region} Stars)")
        pygame.display.flip()
        clock.tick(60)

    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()
