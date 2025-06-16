# pH sensor module for Atlas Scientific EZO circuits
import time

class AtlasScientificPH:
    """Class for communicating with Atlas Scientific pH EZO circuit via I2C"""
    
    def __init__(self, i2c_bus, address=0x63):
        self.i2c = i2c_bus
        self.address = address
    
    def send_command(self, command):
        """Send a command to the EZO circuit"""
        cmd = command.encode("utf-8")
        while not self.i2c.try_lock():
            pass
        try:
            self.i2c.writeto(self.address, cmd)
        finally:
            self.i2c.unlock()
    
    def read_response(self, wait_time=0.9):
        """Read the response from the EZO circuit"""
        time.sleep(wait_time)
        buffer = bytearray(32)
        while not self.i2c.try_lock():
            pass
        try:
            self.i2c.readfrom_into(self.address, buffer)
        finally:
            self.i2c.unlock()
        
        response_code = buffer[0]
        response_string = buffer[1:].decode("utf-8").rstrip('\x00')
        return response_code, response_string
    
    def read_ph(self):
        self.send_command("R")
        code, response = self.read_response()
        if code == 1:
            try:
                return float(response)
            except ValueError:
                return f"Could not convert: {response}"
        else:
            return f"Error (code {code}): {response}"
    
    def get_info(self):
        self.send_command("i")
        code, response = self.read_response(0.3)
        return response
    
    def set_temp_compensation(self, temp_c):
        self.send_command(f"T,{temp_c:.1f}")
        code, response = self.read_response(0.3)
        if code == 1:
            return f"Set to {temp_c:.1f}°C"
        else:
            return f"Error (code {code}): {response}"
    
    def query(self, command, wait_time=0.9):
        self.send_command(command)
        code, response = self.read_response(wait_time)
        self.last_debug = (code, response)
        return response

    def write(self, command):
        """Alias for send_command for compatibility"""
        self.send_command(command)


    
    def calibrate(self, point, value):
        self.send_command(f"Cal,{point},{value:.2f}")
        code, response = self.read_response(1.6)
        return response
    
    def clear_calibration(self):
        self.send_command("Cal,clear")
        code, response = self.read_response(0.3)
        return response
