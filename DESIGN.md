# 바꾸리 A LIGHT / BLUE
Primary: #2E83F2 (RGB 46,131,242), solid fill.
Primary hover: #2475DF, pressed: #1F68CA.
Surface: #FFFFFF, surrounding surface: #F6F8FC.
Text: #26354A; secondary: #718096; dividers: #E2E8F0.
Selection: #EAF3FF. Grid/header: #F7F9FC.
Main layout: top toolbar / expanding file table / format+save mode / status+primary action.
Primary window size 840x650, minimum 760x540 logical px.
No in-content app-name heading.
Popup: 350x264 logical px, transparent window; 100x74 tiles (expansion 110x74), 8px gaps, 12px margins.
Popup tile opacity 225/255, selection 245/255; independent small shadows; theme blue selected-state border independent of keyboard focus.
HWP-only or image-only selection offers center HWPX. Non-XLSX-spreadsheet-only selection offers center XLSX; any XLSX input hides it. ODT uses advanced window for HWPX output.
Icons: editable code-native SVG under assets. Format icon colors retain their format semantics.
User-selected theme: A LIGHT BLUE #2E83F2.

Arrow navigation follows the cross layout: PNG-center-JPEG and PDF-center-more. Hidden center is skipped; outward edges do not wrap. Diagonal outer buttons map to the corresponding arm. Tab order is unchanged.

0.9.0: image/PDF center is compression; HWPX image export lives in the advanced window. Percentage overlay is a separate transparent 180x118 tool window centered on the originating popup, does not activate, and stays visible until completion/cancellation. Main primary action becomes stop while busy. Compression profiles are in settings and the main format bar; JPEG display and .jpeg outputs are canonical.
