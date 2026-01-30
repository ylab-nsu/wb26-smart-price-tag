# pico_display.py - Заглушка для дисплея
class EPD_2in13_B_V4_Landscape:
    def __init__(self):
        self.imageblack = DisplayBuffer()
        self.imagered = DisplayBuffer()
        print("EPD_2in13_B_V4_Landscape initialized (stub)")
    
    def Clear(self, color1, color2):
        print(f"EPD Clear: color1={hex(color1)}, color2={hex(color2)}")
        return
    
    def display(self):
        print("EPD display updated")
        return

class DisplayBuffer:
    def __init__(self):
        self.buffer = bytearray(400 * 300 // 8)  # Примерный размер
    
    def fill(self, color):
        print(f"Buffer fill: {hex(color)}")
    
    def rect(self, x, y, w, h, color):
        print(f"Draw rectangle: ({x},{y}) {w}x{h} color={hex(color)}")
    
    def text(self, text, x, y, color):
        print(f"Draw text: '{text}' at ({x},{y}) color={hex(color)}")
    
    def hline(self, x, y, length, color):
        print(f"Draw horizontal line: ({x},{y}) length={length} color={hex(color)}")