import time
import machine

POT_PIN = 32


pot = machine.ADC(machine.Pin(POT_PIN))
pot.atten(machine.ADC.ATTN_11DB)

while True:
    print(pot.read())
    machine.idle()
    time.sleep(0.1)