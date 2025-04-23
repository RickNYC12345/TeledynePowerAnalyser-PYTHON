import serial
import time
import csv
import os # Import os module to check file existence easily

# --- Configuration ---
port = "COM3"
baud_rate = 115200
averaging_count = 16  # Averaging level (1, 2, 4, 8, 16, 32, 64)
output_csv_file = "power_data_averaged_peakV.csv" # Updated filename

# --- Initialize Serial Connection Variable ---
ser = None

# --- Connect and Configure Instrument ---
try:
    print(f"Attempting to connect to {port} at {baud_rate} baud...")
    ser = serial.Serial(port, baud_rate, timeout=1)
    print(f"Connected successfully to {port}.")

    # Send *IDN? to verify connection and wake up instrument
    ser.write("*IDN?\n".encode())
    time.sleep(0.2)
    idn_response = ser.readline().decode().strip()
    if idn_response:
        print(f"Instrument ID: {idn_response}")
    else:
        print("Warning: No response to *IDN?. Check connection/instrument state.")
        # Consider exiting if IDN fails: raise Exception("Failed to get IDN response")

    # --- NEW: Explicitly define the items to be returned ---
    # We want Item 1 = UPPeak, Item 2 = I, Item 3 = P
    # Using mixed case for set commands based on previous observations
    print("Setting measurement items: 1=UPPeak, 2=I, 3=P...")
    ser.write(":NUMeric:NORMal:ITEM1 UPPeak\n".encode()) # Set Item 1 to Positive Peak Voltage
    time.sleep(0.2) # Allow time for processing
    ser.write(":NUMeric:NORMal:ITEM2 I\n".encode())      # Set Item 2 to Current
    time.sleep(0.2)
    ser.write(":NUMeric:NORMal:ITEM3 P\n".encode())      # Set Item 3 to Active Power
    time.sleep(0.2)

    # Optional: Query items to confirm (using ALL CAPS for query)
    print("Querying item settings for confirmation...")
    ser.write(":NUMERIC:NORMAL:ITEM1?\n".encode())
    time.sleep(0.1)
    item1_resp = ser.readline().decode().strip()
    print(f"Confirmation item 1: '{item1_resp}' (Expected :NUM:NORM:ITEM1 UPPE)") # Note: Instrument might abbreviate response
    ser.write(":NUMERIC:NORMAL:ITEM2?\n".encode())
    time.sleep(0.1)
    item2_resp = ser.readline().decode().strip()
    print(f"Confirmation item 2: '{item2_resp}' (Expected :NUM:NORM:ITEM2 I)")
    ser.write(":NUMERIC:NORMAL:ITEM3?\n".encode())
    time.sleep(0.1)
    item3_resp = ser.readline().decode().strip()
    print(f"Confirmation item 3: '{item3_resp}' (Expected :NUM:NORM:ITEM3 P)")
    # --- End NEW section ---


    # Now, manage the *number* of items returned (should be 3)
    print("Checking/Setting number of items to return to 3...")
    ser.write(":NUMERIC:NORMAL:NUMBER?\n".encode()) # Query first
    time.sleep(0.1)
    number_response_raw = ser.readline().decode().strip()
    print(f"Response for NUMBER query: '{number_response_raw}'")
    number_response_val = -1
    if number_response_raw:
        try:
            number_response_val = int(number_response_raw.split()[-1])
            print(f"Current number of items reported: {number_response_val}")
        except (IndexError, ValueError):
            print(f"Could not parse number of items from response: '{number_response_raw}'")
    else:
        print("Warning: No response received for :NUMERIC:NORMAL:NUMBER? query.")

    # Set number of items if not already 3
    if number_response_val != 3:
        print("Setting number of items to 3...")
        ser.write(":NUMeric:NORMal:NUMBer 3\n".encode()) # Set command
        time.sleep(0.2)
        # Confirm the change
        ser.write(":NUMERIC:NORMAL:NUMBER?\n".encode()) # Query again
        time.sleep(0.1)
        confirm_response = ser.readline().decode().strip()
        print(f"Confirmation response after setting NUMBER: '{confirm_response}'")
    else:
        print("Number of items is already 3.")


    # Set Averaging Count (using mixed case for set command)
    print(f"Setting averaging count to: {averaging_count}")
    ser.write(f":MEASure:AVERaging:COUNt {averaging_count}\n".encode())
    time.sleep(0.2)

    # Confirm the averaging setting (using ALL CAPS for query)
    ser.write(":MEASURE:AVERAGING:COUNT?\n".encode())
    time.sleep(0.1)
    avg_response = ser.readline().decode().strip()
    if avg_response:
        print(f"Averaging count confirmation response: '{avg_response}'")
    else:
         print("Warning: No response received for :MEASURE:AVERAGING:COUNT? query.")


except serial.SerialException as e:
    print(f"Fatal Error: Serial communication error during configuration: {e}")
    if ser and ser.is_open:
        ser.close()
    exit() # Exit if configuration fails
except Exception as e:
    print(f"Fatal Error: An unexpected error occurred during configuration: {e}")
    if ser and ser.is_open:
        ser.close()
    exit() # Exit if configuration fails


# --- Measurement Loop and CSV Logging ---
print(f"\nStarting measurement loop. Logging data to '{output_csv_file}'...")

try:
    with open(output_csv_file, "a", newline='') as csvfile:
        writer = csv.writer(csvfile)

        file_is_empty = os.path.getsize(output_csv_file) == 0 if os.path.exists(output_csv_file) else True

        if file_is_empty:
            print("CSV file is new or empty. Writing header.")
            # --- UPDATED CSV HEADER ---
            writer.writerow(["Timestamp", "Avg Peak Voltage (V+pk)", "Avg Current (A)", "Avg Power (W)"])
            csvfile.flush()

        while True:
            try:
                # Query measurements (Items 1, 2, 3 are now UPPeak, I, P)
                ser.write(":NUMERIC:NORMAL:VALUE?\n".encode()) # Query is ALL CAPS
                response = ser.readline().decode().strip()

                if response:
                    try:
                        values = response.split(",")
                        if len(values) >= 3:
                            # Parse the values
                            peak_voltage = float(values[0]) # Value 1 is now UPPeak
                            current = float(values[1])      # Value 2 is I
                            power = float(values[2])        # Value 3 is P
                            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

                            # --- UPDATED PRINT STATEMENT ---
                            print(f"{timestamp} - Avg V+pk: {peak_voltage:.4f} V, Avg I: {current:.4f} A, Avg P: {power:.4f} W")

                            # Write data row to CSV (using updated labels implicitly via header)
                            writer.writerow([timestamp, peak_voltage, current, power])
                            csvfile.flush()

                        else:
                            print(f"Warning: Received unexpected number of values: {len(values)}. Response: '{response}'")

                    except (ValueError, IndexError) as e:
                        print(f"Error parsing response: '{response}'. Error: {e}")
                    except Exception as e:
                         print(f"An unexpected error occurred during data processing/writing: {e}")

                else:
                    print("Warning: No measurement response received from instrument in this cycle.")

                time.sleep(1) # Poll every second

            except serial.SerialException as e:
                print(f"\nSerial communication error during loop: {e}")
                print("Exiting measurement loop due to serial error.")
                break
            except IOError as e:
                 print(f"\nError writing to CSV file '{output_csv_file}': {e}")
                 print("Exiting measurement loop due to file error.")
                 break
            except Exception as e:
                print(f"\nAn unexpected error occurred in the measurement loop: {e}")
                break

# --- Cleanup ---
except KeyboardInterrupt:
    print("\nCtrl+C detected. Stopping data logging.")
except IOError as e:
    print(f"Fatal Error: Could not open or write to CSV file '{output_csv_file}': {e}")
finally:
    if ser and ser.is_open:
        print("Closing serial port.")
        ser.close()
    print("Script finished.")
