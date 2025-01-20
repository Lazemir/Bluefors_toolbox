// ---------------------------------------------------------------------------
// DESCRIPTION
// ---------------------------------------------------------------------------

#include <EEPROM.h>
#include <NewPing.h>
#include "Vrekrer_scpi_parser.h"

#define TRIGGER_PIN  3  // Arduino pin tied to trigger pin on the ultrasonic sensor.
#define ECHO_PIN     2  // Arduino pin tied to echo pin on the ultrasonic sensor.
#define MAX_DISTANCE 255 // Maximum distance we want to ping for (in centimeters). Maximum sensor distance is rated at 400-500cm.

// #define RED_LED_PIN    5
// #define GREEN_LED_PIN  6

// #define PING_INTERVAL  600000
#define PING_COUNT 1

#define EMPTY_LEVEL_ADDR 0
#define FULL_LEVEL_ADDR 1

byte empty_level, full_level;

unsigned long lastPingTime = 0;

SCPI_Parser instrument;
NewPing sonar(TRIGGER_PIN, ECHO_PIN, MAX_DISTANCE); // NewPing setup of pins and maximum distance.

void _put_to_eeprom(byte value, byte& variable, const byte& eeprom_address) {
  variable = value;
  EEPROM.put(eeprom_address, value);
}

byte _measure_distance() {
  return byte(sonar.ping_median(PING_COUNT) / US_ROUNDTRIP_CM);
}

float _measure_level() {
  byte current_distance = _measure_distance();
  if (!current_distance || empty_level == full_level) return NAN;
  return float(empty_level - current_distance) / (empty_level - full_level);
}


void MeasureDistance(SCPI_C commands, SCPI_P parameters, Stream& interface) {
  interface.println(_measure_distance());
}

void MeasureLevel(SCPI_C commands, SCPI_P parameters, Stream& interface) {
  interface.println(_measure_level());
}

void GetEmptyLevel(SCPI_C commands, SCPI_P parameters, Stream& interface) {
  interface.println(empty_level);
}

void GetFullLevel(SCPI_C commands, SCPI_P parameters, Stream& interface) {
  interface.println(full_level);
}

void SetLevel(SCPI_C commands, SCPI_P parameters, Stream& interface) {
  byte level;
  if (!parameters.Size()) {
    level = _measure_distance();
  }
  level = constrain(String(parameters[0]).toInt(), 0, MAX_DISTANCE);
  String last_header = String(commands.Last());
  last_header.toUpperCase();
  if (last_header.startsWith("EMP")) {
    _put_to_eeprom(level, empty_level, EMPTY_LEVEL_ADDR);
  } else if (last_header.startsWith("FULL")) {
    _put_to_eeprom(level, full_level, FULL_LEVEL_ADDR);
  }
}

void Identify(SCPI_C commands, SCPI_P parameters, Stream& interface) {
  interface.println(F("Vrekrer,Configuration options example,#00," 
                      VREKRER_SCPI_VERSION));
}

void setup() {
  EEPROM.get(EMPTY_LEVEL_ADDR, empty_level);
  EEPROM.get(FULL_LEVEL_ADDR, full_level);

  instrument.SetCommandTreeBase(F(":DISTance"));
    instrument.RegisterCommand(F(":MEASure?"), &MeasureDistance);
  instrument.SetCommandTreeBase(F(":LEVel"));
    instrument.RegisterCommand(F(":MEASure?"), &MeasureLevel);
  instrument.SetCommandTreeBase(F(":LEVel:SETup"));
    instrument.RegisterCommand(F(":EMPty?"), &GetEmptyLevel);
    instrument.RegisterCommand(F(":EMPty"), &SetLevel);
    instrument.RegisterCommand(F(":FULL?"), &GetFullLevel);
    instrument.RegisterCommand(F(":FULL"), &SetLevel);
  instrument.SetCommandTreeBase(F(""));
    instrument.RegisterCommand(F("*IDN?"), &Identify);

  Serial.begin(115200);
  while (!Serial) {;}

  // instrument.PrintDebugInfo(Serial);
}

void loop() {
  instrument.ProcessInput(Serial, "\n");
}
