import sys

for evtValue in sys.argv[1:]:
    # evtValue = 0x000F7A66000001EF
    evtValue = int(evtValue, 16)
    evtType = (evtValue & 0xF << 60) >> 60
    match (evtType):
        case 0x8:
            evtTime = evtValue
            evtTimeMask = (evtValue & 0xFFFFFFF << 32) >> 32
            evtTime = evtTimeMask << 6
            print(f"Time High Event: {evtTime}us, mask: {evtTimeMask:028b}")
        case 0x0:
            evtTime = (evtValue & 0x3F << 54) >> 54
            evtPosX = (evtValue & 0x7FF << 43) >> 43
            evtPosY = (evtValue & 0x7FF << 32) >> 32
            evtPixelMask = evtValue & 0xFFFFFFFF
            print(
                f"Negative Event: {evtTime}us, x:{evtPosX}, y:{evtPosY}, mask: 0b{evtPixelMask:032b}, 0x{evtPixelMask:08x} "
            )
        case 0x1:
            evtTime = (evtValue & 0x3F << 54) >> 54
            evtPosX = (evtValue & 0x7FF << 43) >> 43
            evtPosY = (evtValue & 0x7FF << 32) >> 32
            evtPixelMask = evtValue & 0xFFFFFFFF
            print(
                f"Positive Event: {evtTime}us, x:{evtPosX}, y:{evtPosY}, mask: 0b{evtPixelMask:032b}, 0x{evtPixelMask:08x} "
            )
        case 0xA:
            print("External Trigger Event")
        case _:
            print("Not valid event type!")
