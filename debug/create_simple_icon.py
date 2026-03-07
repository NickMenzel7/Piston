#!/usr/bin/env python
"""
Create a simple multi-size icon for Piston app.
Requires: pip install pillow
"""
from PIL import Image, ImageDraw, ImageFont
import os

def create_simple_icon():
    """Create a simple multi-size .ico file with a 'P' letter."""
    sizes = [(16, 16), (32, 32), (48, 48), (256, 256)]
    images = []
    
    for size in sizes:
        # Create image with dark background
        img = Image.new('RGBA', size, (30, 30, 30, 255))
        draw = ImageDraw.Draw(img)
        
        # Draw a circle
        margin = size[0] // 8
        draw.ellipse([margin, margin, size[0]-margin, size[1]-margin], 
                     fill=(0, 125, 165, 255), outline=(255, 255, 255, 255))
        
        # Draw 'P' letter (simple version without font)
        # Draw white 'P' manually
        w, h = size
        center_x = w // 2
        center_y = h // 2
        
        # Simple geometric 'P' - white rectangles
        # Vertical bar
        bar_width = w // 6
        bar_height = h // 2
        draw.rectangle([center_x - bar_width, center_y - bar_height//2,
                       center_x, center_y + bar_height//2], 
                      fill=(255, 255, 255, 255))
        
        # Top curve (simplified as rectangle)
        curve_width = w // 4
        curve_height = h // 6
        draw.rectangle([center_x, center_y - bar_height//2,
                       center_x + curve_width, center_y - bar_height//2 + curve_height], 
                      fill=(255, 255, 255, 255))
        draw.rectangle([center_x + curve_width - bar_width//2, center_y - bar_height//2,
                       center_x + curve_width, center_y], 
                      fill=(255, 255, 255, 255))
        
        images.append(img)
    
    # Save as multi-size .ico
    output_path = 'Icon/piston-16.ico'
    images[0].save(output_path, format='ICO', sizes=[(img.width, img.height) for img in images], 
                   append_images=images[1:])
    
    print(f"✓ Created multi-size icon at: {output_path}")
    print(f"  Sizes: {[img.size for img in images]}")
    
    # Check file size
    size_kb = os.path.getsize(output_path) / 1024
    print(f"  File size: {size_kb:.1f} KB")
    
    if size_kb > 10:
        print("✓ Icon is large enough (multi-size)")
    else:
        print("⚠ Icon might be too small")

if __name__ == '__main__':
    try:
        create_simple_icon()
        print("\n✓ Icon created! Now rebuild with PyInstaller.")
    except ImportError:
        print("❌ Error: Pillow not installed")
        print("   Install it: pip install pillow")
    except Exception as e:
        print(f"❌ Error: {e}")
