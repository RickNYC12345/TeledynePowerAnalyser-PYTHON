import serial
import time
import csv
import os
import sys # Import sys for exit

# --- Configuration ---
port = '/dev/cu.usbmodemT0415C223200611' # <<< CHECK/UPDATE YOUR SERIAL PORT
baud_rate = 115200
integration_interval_seconds = 10 # <<< SET YOUR DESIRED INTEGRATION TIME HERE (seconds)
output_csv_file = f"power_data_integrated_{integration_interval_seconds}s.csv" # Dynamic filename in script directory

# --- Initialize Serial Connection Variable ---
ser = None

# --- Helper function to convert seconds to H,M,S for timer command ---
def seconds_to_hms(seconds):
    """Converts seconds to hours, minutes, seconds tuple for SCPI timer command."""
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    # Clamp hours to max 9999 per SCPI spec (if applicable to your model)
    h = min(h, 9999)
    return int(h), int(m), int(s)

# --- Function to safely write to serial and handle potential errors ---
def safe_serial_write(ser_conn, command):
    """Sends a command to the serial port and handles potential write errors."""
    try:
        # print(f"SEND: {command.strip()}") # Uncomment for debugging writes
        ser_conn.write(command.encode())
        time.sleep(0.1) # Small delay after write seems necessary for some devices
        return True
    except serial.SerialTimeoutException:
        print(f"Error: Serial write timeout sending command: {command.strip()}")
        return False
    except serial.SerialException as e:
        print(f"Error: Serial write error sending command: {command.strip()} - {e}")
        return False
    except Exception as e:
        print(f"Error: Unexpected error sending command: {command.strip()} - {e}")
        return False

# --- Function to safely read from serial ---
def safe_serial_read(ser_conn):
    """Reads a line from the serial port, handling potential errors and timeouts."""
    try:
        response_bytes = ser_conn.readline()
        if response_bytes:
            response_str = response_bytes.decode().strip()
            # print(f"RECV: {response_str}") # Uncomment for debugging reads
            return response_str
        else:
            # print("Warning: Serial readline timed out (received no data).") # More verbose warning if needed
            return None # Indicates timeout or no data
    except serial.SerialException as e:
        print(f"Error: Serial read error: {e}")
        return None # Indicate error
    except UnicodeDecodeError as e:
        print(f"Error: Could not decode received bytes: {response_bytes}. Error: {e}")
        return None # Indicate decode error
    except Exception as e:
        print(f"Error: Unexpected error during serial read: {e}")
        return None # Indicate other error

# --- Connect and Configure Instrument ---
try:
    print(f"Attempting to connect to {port} at {baud_rate} baud...")
    # Increase timeout slightly for potentially slower responses during configuration/polling
    ser = serial.Serial(port, baud_rate, timeout=2)
    print(f"Connected successfully to {port}.")
    time.sleep(0.5) # Give the connection a moment to stabilize

    # Send *IDN? to verify connection (Standard queries often uppercase)
    if not safe_serial_write(ser, "*IDN?\n"): raise Exception("Failed to send *IDN?")
    idn_response = safe_serial_read(ser)
    if idn_response:
        print(f"Instrument ID: {idn_response}")
        # Basic check if it looks like a Teledyne/LeCroy device (optional)
        if "TELEDYNE" not in idn_response.upper() and "LECROY" not in idn_response.upper():
             print("Warning: Instrument ID doesn't obviously mention Teledyne/LeCroy. Ensure compatibility.")
    else:
        print("Warning: No response to *IDN?. Check connection/instrument state/permissions.")
        raise Exception("Failed to get IDN response")

    # --- Configure Integration Settings ---
    print("\nConfiguring Integration Settings...")
    # Mode = STANdard (Timed) - Set command (mixed case)
    if not safe_serial_write(ser, ":INTegrate:MODE STANdard\n"): raise Exception("Failed to set integrate mode")
    # Function = WATT (for Watt-hours) - Set command (mixed case)
    if not safe_serial_write(ser, ":INTegrate:FUNCtion WATT\n"): raise Exception("Failed to set integrate function")
    # Timer Interval - Set command (mixed case)
    h, m, s = seconds_to_hms(integration_interval_seconds)
    timer_cmd = f":INTegrate:TIMer {h},{m},{s}\n"
    print(f"Setting integration timer to {h}h {m}m {s}s ({integration_interval_seconds} seconds)")
    if not safe_serial_write(ser, timer_cmd): raise Exception("Failed to set integrate timer")
    time.sleep(0.2) # Extra delay after timer set

    # Optional: Query settings to confirm (Query commands ALL CAPS)
    if safe_serial_write(ser, ":INTEGRATE:MODE?\n"):
        print(f"Confirm Mode: {safe_serial_read(ser)}")
    if safe_serial_write(ser, ":INTEGRATE:FUNCTION?\n"):
        print(f"Confirm Function: {safe_serial_read(ser)}")
    if safe_serial_write(ser, ":INTEGRATE:TIMER?\n"):
        print(f"Confirm Timer: {safe_serial_read(ser)}")


    # --- Configure Numeric Items ---
    # Item 1=UPPeak, Item 2=I, Item 3=P (instantaneous), Item 4=WH (integrated Watt-Hours)
    # Set commands (mixed case)
    print("\nConfiguring Numeric Items (1:Vpk, 2:I, 3:P_inst, 4:WH_int)...")
    if not safe_serial_write(ser, ":NUMeric:NORMal:ITEM1 UPPeak\n"): raise Exception("Failed to set NUM ITEM1")
    if not safe_serial_write(ser, ":NUMeric:NORMal:ITEM2 I\n"): raise Exception("Failed to set NUM ITEM2")
    if not safe_serial_write(ser, ":NUMeric:NORMal:ITEM3 P\n"): raise Exception("Failed to set NUM ITEM3") # Keep instantaneous P as item 3
    if not safe_serial_write(ser, ":NUMeric:NORMal:ITEM4 WH\n"): raise Exception("Failed to set NUM ITEM4") # Add total Watt-Hours as item 4

    # Set number of items to return to 4 - Set command (mixed case)
    if not safe_serial_write(ser, ":NUMeric:NORMal:NUMBer 4\n"): raise Exception("Failed to set NUM NUMBER")
    # Confirm number of items - Query command (ALL CAPS)
    if safe_serial_write(ser, ":NUMERIC:NORMAL:NUMBER?\n"):
        print(f"Confirm Number of Items: {safe_serial_read(ser)}")

    # --- Disable Averaging (Optional - focus on Integration) ---
    # print("\nSetting instantaneous averaging count to 1 (disabling averaging)")
    # if not safe_serial_write(ser, ":MEASure:AVERaging:COUNt 1\n"): # Set command (mixed case)
    #     print("Warning: Failed to disable averaging.")
    # else:
    #     if safe_serial_write(ser, ":MEASURE:AVERAGING:COUNT?\n"): # Query command (ALL CAPS)
    #         print(f"Confirm Averaging Count: {safe_serial_read(ser)}")


except serial.SerialException as e:
    print(f"Fatal Error: Serial communication error during configuration: {e}")
    if ser and ser.is_open:
        ser.close()
    sys.exit(1) # Use sys.exit for cleaner termination
except Exception as e:
    print(f"Fatal Error: An unexpected error occurred during configuration: {e}")
    if ser and ser.is_open:
        ser.close()
    sys.exit(1)


# --- Measurement Loop using Integration ---
print(f"\nStarting Integration Loop. Interval: {integration_interval_seconds}s. Logging to '{output_csv_file}'...")

csv_writer = None
csv_file_handle = None

try:
    # Open CSV file and prepare writer
    # Check if file exists to write header
    file_exists = os.path.exists(output_csv_file)
    file_is_empty = not file_exists or os.path.getsize(output_csv_file) == 0

    # Use 'a' mode to append if exists, 'w' if not (though 'a' works for new files too)
    csv_file_handle = open(output_csv_file, "a", newline='')
    csv_writer = csv.writer(csv_file_handle)

    if file_is_empty:
        print("CSV file is new or empty. Writing header.")
        # --- UPDATED CSV HEADER ---
        csv_writer.writerow([
            "Timestamp",
            "Interval Avg Power (W)",
            "Interval WattHours (Wh)",
            "End Interval V+pk (V)",
            "End Interval Current (A)",
            "End Interval Inst Power (W)"
        ])
        csv_file_handle.flush() # Ensure header is written immediately

    loop_count = 0
    while True:
        loop_count += 1
        print(f"\n--- Starting Integration Cycle {loop_count} ---")
        integration_start_time = time.time()
        cycle_error = False # Flag to track if an error occurred within this cycle

        try:
            # 1. Reset Integrator - Set command (mixed case)
            print("Resetting integrator...")
            if not safe_serial_write(ser, ":INTegrate:RESet\n"):
                raise Exception("Failed to send RESET command")
            time.sleep(0.3) # Give it a moment to reset

            # 2. Start Integrator - Set command (mixed case)
            print("Starting integrator...")
            if not safe_serial_write(ser, ":INTegrate:STARt\n"):
                 raise Exception("Failed to send START command")
            time.sleep(0.1) # Small delay after start

            # 3. Wait for Integration to complete by polling state
            print(f"Integrating for {integration_interval_seconds} seconds...")
            polling_start_time = time.time()
            software_timeout_seconds = integration_interval_seconds * 1.5 + 5 # Base timeout + grace period
            last_state_print_time = 0

            while True:
                current_time = time.time()

                # Check for software timeout first
                if current_time - polling_start_time > software_timeout_seconds:
                    raise TimeoutError(f"Integration polling software timeout ({software_timeout_seconds:.1f}s) waiting for TIMEUP/TIM state.")

                # Query state command (ALL CAPS)
                if not safe_serial_write(ser, ":INTEGRATE:STATE?\n"):
                    # If sending query fails, wait briefly and retry, but don't loop forever
                    print("Warning: Failed to send STATE query. Retrying...")
                    time.sleep(1.0)
                    if time.time() - polling_start_time > software_timeout_seconds: # Recheck timeout after sleep
                         raise TimeoutError(f"Integration polling software timeout ({software_timeout_seconds:.1f}s) after failing to send STATE query.")
                    continue # Go back to start of while loop to retry write

                # Read response
                state_response = safe_serial_read(ser)

                if state_response is None:
                    # Read failed (e.g., timeout on readline)
                    print("Warning: No response received for STATE query (read timeout). Retrying...")
                    # No need to sleep here, safe_serial_read already waited for its timeout
                    # Check timeout again immediately after failed read
                    if time.time() - polling_start_time > software_timeout_seconds:
                         raise TimeoutError(f"Integration polling software timeout ({software_timeout_seconds:.1f}s) after failing to read STATE response.")
                    continue # Go back to start of while loop to retry query

                # Process valid response
                state_response_upper = state_response.upper()

                # Optional: Print state less frequently to avoid spamming console
                if current_time - last_state_print_time > 2.0: # Print state every 2 seconds
                    print(f"  Current state: {state_response_upper} (Polling duration: {current_time - polling_start_time:.1f}s)")
                    last_state_print_time = current_time

                # --- CORRECTED STATE CHECKING ---
                if "TIM" in state_response_upper or "TIMEUP" in state_response_upper: # Accept TIM or TIMEUP
                    print(f"Integration complete ({state_response_upper}).")
                    break # Exit the polling loop successfully
                elif "RUN" in state_response_upper or "RUNNING" in state_response_upper: # Accept RUN or RUNNING
                    # State is as expected (running), wait briefly and poll again
                    time.sleep(0.4) # Poll slightly less frequently than 0.5s
                elif "STOP" in state_response_upper or "RESET" in state_response_upper:
                    print(f"Error: Integration stopped unexpectedly. State: {state_response_upper}")
                    raise Exception(f"Integration stopped unexpectedly: {state_response_upper}")
                elif "OVERFLOW" in state_response_upper:
                     print(f"Error: Integration overflow detected. State: {state_response_upper}")
                     raise Exception(f"Integration overflow: {state_response_upper}")
                else:
                    # Handle truly unexpected states if needed, otherwise just log and wait
                    # Avoid flooding with warnings - maybe print only once per unique unexpected state?
                    print(f"Warning: Unexpected integration state received: {state_response_upper}. Continuing to wait...")
                    time.sleep(0.5)
                # --- END CORRECTED STATE CHECKING ---

            # End of polling loop (break was called)

            # 4. Query the Numeric Values - Query command (ALL CAPS)
            print("Querying measurement results...")
            if not safe_serial_write(ser, ":NUMERIC:NORMAL:VALUE?\n"):
                 raise Exception("Failed to send numeric query")

            response = safe_serial_read(ser)

            if response:
                try:
                    values = response.split(",")
                    if len(values) >= 4:
                        # Convert to float, handle potential conversion errors
                        peak_voltage = float(values[0]) if values[0] else 0.0
                        current = float(values[1]) if values[1] else 0.0
                        instant_power = float(values[2]) if values[2] else 0.0
                        watt_hours = float(values[3]) if values[3] else 0.0

                        # 5. Calculate Average Power over the interval
                        # Use the actual configured interval time for calculation
                        interval_hours = integration_interval_seconds / 3600.0
                        if interval_hours > 1e-9: # Avoid division by zero or near-zero
                            average_power = watt_hours / interval_hours
                        else:
                            average_power = 0.0 # Or handle as error/undefined

                        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

                        # Print to console
                        print(f"{timestamp} - Interval Avg P: {average_power:.4f} W (from {watt_hours:.6f} Wh)")
                        print(f"             End V+pk: {peak_voltage:.4f} V, End I: {current:.4f} A, End Inst P: {instant_power:.4f} W")

                        # Write data row to CSV
                        if csv_writer and csv_file_handle:
                             csv_writer.writerow([
                                timestamp,
                                f"{average_power:.4f}",
                                f"{watt_hours:.6f}",
                                f"{peak_voltage:.4f}",
                                f"{current:.4f}",
                                f"{instant_power:.4f}"
                            ])
                             csv_file_handle.flush() # Ensure data is written to disk
                        else:
                            print("Error: CSV file not available for writing.")
                            cycle_error = True # Mark cycle as having an error


                    else:
                        print(f"Warning: Received unexpected number of values: {len(values)}. Response: '{response}'")
                        cycle_error = True # Mark cycle as having an error

                except (ValueError, IndexError) as e:
                    print(f"Error parsing measurement response: '{response}'. Error: {e}")
                    cycle_error = True # Mark cycle as having an error
                except Exception as e:
                     print(f"An unexpected error occurred during data processing/writing: {e}")
                     cycle_error = True # Mark cycle as having an error
            else:
                print("Warning: No measurement response received after integration.")
                cycle_error = True # Mark cycle as having an error

        # --- Inner Exception Handling (for single cycle errors) ---
        except serial.SerialException as e:
            print(f"\nSerial communication error during loop cycle {loop_count}: {e}")
            print("Attempting to continue to next cycle if possible, otherwise exiting.")
            cycle_error = True
            # Consider adding logic here to try and reconnect or decide to exit the main loop
            break # Exit main loop on serial error for now
        except IOError as e:
             print(f"\nError writing to CSV file '{output_csv_file}' during cycle {loop_count}: {e}")
             print("Exiting measurement loop due to file error.")
             cycle_error = True
             break # Exit main loop
        except TimeoutError as e:
             print(f"\nTimeout Error during cycle {loop_count}: {e}")
             print("Exiting measurement loop.")
             cycle_error = True
             break # Exit main loop
        except Exception as e:
            print(f"\nAn unexpected error occurred in integration cycle {loop_count}: {e}")
            print("Attempting to proceed to next cycle.")
            cycle_error = True
            # Maybe add a small delay before the next cycle after an error
            time.sleep(1.0)

        if cycle_error:
             print(f"--- Cycle {loop_count} completed with errors ---")
        else:
             print(f"--- Cycle {loop_count} completed successfully ---")

        # Optional: Add a small delay between successful cycles if needed
        # time.sleep(0.5)


# --- Main Exception Handling (for loop exit conditions) ---
except KeyboardInterrupt:
    print("\nCtrl+C detected. Stopping measurement loop.")
except Exception as e:
    # This catches errors that might happen outside the inner try/except,
    # like the initial CSV file opening.
    print(f"An unexpected error occurred outside the main loop: {e}")


# --- Cleanup ---
finally:
    print("\n--- Script Finalizing ---")
    if csv_file_handle:
        print(f"Closing CSV file: '{output_csv_file}'")
        csv_file_handle.close()

    if ser and ser.is_open:
        try:
            print("Attempting to stop integrator (if running)...")
            # Send STOP command (mixed case) - Best effort
            # Use a short timeout for this final command
            ser.timeout = 0.5 # Temporarily reduce timeout
            if not safe_serial_write(ser, ":INTegrate:STOP\n"):
                print("Warning: Could not send STOP command reliably.")
            else:
                # Optionally read response if STOP sends one, otherwise just assume it worked
                # stop_response = safe_serial_read(ser)
                # print(f"Stop response (if any): {stop_response}")
                pass
        except Exception as stop_e:
            print(f"Could not send stop command during cleanup: {stop_e}")
        finally:
             print("Closing serial port.")
             ser.close()
    else:
        print("Serial port was not open or already closed.")

    print("Script finished.")
    sys.exit(0) # Indicate successful completion (or controlled exit)
