/*
 * smart_agro_esp32.ino
 * =====================
 * Updated:
 * - Fast PIR response
 * - HTTP POST every 5 sec (non-blocking)
 * - Better error handling
 */

#include <DHT.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>

// ── WiFi Credentials ──────────────────────────────────────────────
#define WIFI_SSID      "Xiaomi 11i"
#define WIFI_PASSWORD  "[PASSWORD]"
#define SERVER_URL "http://[IP_ADDRESS]/api/sensor"

// ── Pin Definitions ───────────────────────────────────────────────
#define DHTPIN     4
#define DHTTYPE    DHT11

#define PIR_PIN    13
#define FLAME_PIN  14
#define SOIL_PIN   34
#define BUZZER_PIN 25

// ── Initialize DHT ────────────────────────────────────────────────
DHT dht(DHTPIN, DHTTYPE);

// Timer for HTTP post
unsigned long lastPostTime = 0;
const unsigned long postInterval = 5000;

// ── Setup ─────────────────────────────────────────────────────────
void setup() {
  Serial.begin(115200);

  pinMode(PIR_PIN, INPUT);
  pinMode(FLAME_PIN, INPUT);
  pinMode(SOIL_PIN, INPUT);
  pinMode(BUZZER_PIN, OUTPUT);

  dht.begin();

  Serial.println("ESP32 Sensor System Initialized");

  // Connect WiFi
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  Serial.print("Connecting to WiFi");

  int attempts = 0;

  while (WiFi.status() != WL_CONNECTED && attempts < 30) {
    delay(500);
    Serial.print(".");
    attempts++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println();
    Serial.print("Connected: ");
    Serial.println(WiFi.localIP());

    tone(BUZZER_PIN, 1000, 100);
    delay(200);
    tone(BUZZER_PIN, 1500, 100);
    delay(200);
    noTone(BUZZER_PIN);
  }
  else {
    Serial.println("\nWiFi failed");
  }
}

// ── Loop ──────────────────────────────────────────────────────────
void loop() {

  // Read DHT
  float temp = dht.readTemperature();
  float hum  = dht.readHumidity();

  if (isnan(temp) || isnan(hum)) {
    Serial.println("DHT read failed");
    return;
  }

  // Read PIR
  int pirState = digitalRead(PIR_PIN);

  // Read Flame
  int flameState = digitalRead(FLAME_PIN);

  // Read Soil
  int soilValue = analogRead(SOIL_PIN);

  int soilPercent = map(soilValue, 4095, 3000, 0, 100);
  soilPercent = constrain(soilPercent, 0, 100);

  // Serial Output
  Serial.println("-------------");
  Serial.print("Temp: ");
  Serial.print(temp);
  Serial.println(" C");

  Serial.print("Humidity: ");
  Serial.print(hum);
  Serial.println(" %");

  Serial.print("PIR: ");
  Serial.println(pirState == HIGH ? "Detected" : "Not Detected");

  Serial.print("Flame: ");
  Serial.println(flameState == HIGH ? "Detected" : "Not Detected");

  Serial.print("Soil Raw: ");
  Serial.println(soilValue);

  Serial.print("Soil Moisture: ");
  Serial.print(soilPercent);
  Serial.println(" %");

  // Buzzer only for flame
  if (flameState == HIGH) {
    tone(BUZZER_PIN, 2000);
  } else {
    noTone(BUZZER_PIN);
  }

  // Reconnect WiFi if disconnected
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("WiFi disconnected. Reconnecting...");
    WiFi.reconnect();
  }

  // Send HTTP every 5 seconds
  if (millis() - lastPostTime >= postInterval) {

    lastPostTime = millis();

    if (WiFi.status() == WL_CONNECTED) {

      HTTPClient http;

      http.begin(SERVER_URL);
      http.addHeader("Content-Type", "application/json");
      http.setTimeout(5000);

      StaticJsonDocument<256> doc;

      doc["temperature"] = temp;
      doc["humidity"] = hum;
      doc["soil_moisture"] = soilPercent;
      doc["pir_motion"] = (pirState == HIGH);
      doc["flame_detected"] = (flameState == HIGH);
      doc["light_intensity"] = 0;
      doc["co2_ppm"] = 400;

      String body;
      serializeJson(doc, body);

      Serial.println("Sending JSON:");
      Serial.println(body);

      int httpCode = http.POST(body);

      if (httpCode > 0) {
        Serial.print("HTTP Code: ");
        Serial.println(httpCode);

        String response = http.getString();
        Serial.println(response);
      }
      else {
        Serial.print("HTTP Error: ");
        Serial.println(http.errorToString(httpCode));
      }

      http.end();
    }
  }

  // Fast PIR response
  delay(200);
}