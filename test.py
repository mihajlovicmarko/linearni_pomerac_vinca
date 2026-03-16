import serial

ser = serial.Serial("COM3", 9600, timeout=1)

ser.write(b"0gs\r\n")
print(ser.readline())

ser.close()