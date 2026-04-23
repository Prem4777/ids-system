#include <WiFi.h>
#include <HTTPClient.h>
#include <DHT.h>

// WiFi credentials
const char* ssid = "OnePlus Nord 5";
const char* password = "onetwoeight";

// Backend base URLs (Phase 3 FastAPI). Device will fail over automatically.
const char* primaryBackendBaseUrl = "http://10.145.0.209:8000";
const char* secondaryBackendBaseUrl = "http://10.93.126.49:8000";

// Device identity
const char* deviceId = "esp32-dht11-1";

// Hardware pins
#define DHTPIN 4
#define DHTTYPE DHT11
#define BUZZER_PIN 5

DHT dht(DHTPIN, DHTTYPE);

unsigned long lastPublishMs = 0;
const unsigned long publishIntervalMs = 5000;
String activeBackend = primaryBackendBaseUrl;

bool isHttpOk(int code) {
  return code >= 200 && code < 300;
}

String makeUrl(const String& base, const char* path) {
  return base + String(path);
}

void connectWiFi() {
  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);

  Serial.print("Connecting to WiFi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println();
  Serial.print("Connected. IP: ");
  Serial.println(WiFi.localIP());
}

bool postSensorDataTo(const String& baseUrl, float temperature, float humidity) {
  HTTPClient http;
  String sensorUrl = makeUrl(baseUrl, "/sensor");

  http.begin(sensorUrl);
  http.addHeader("Content-Type", "application/json");

  String jsonData = "{";
  jsonData += "\"temperature\":" + String(temperature, 2) + ",";
  jsonData += "\"humidity\":" + String(humidity, 2) + ",";
  jsonData += "\"device_id\":\"" + String(deviceId) + "\"";
  jsonData += "}";

  int code = http.POST(jsonData);
  String response = http.getString();
  http.end();

  Serial.print("POST /sensor [");
  Serial.print(baseUrl);
  Serial.print("] code: ");
  Serial.println(code);
  Serial.print("POST /sensor response: ");
  Serial.println(response);

  return isHttpOk(code);
}

bool postSensorData(float temperature, float humidity) {
  if (postSensorDataTo(activeBackend, temperature, humidity)) {
    return true;
  }

  String fallback = (activeBackend == primaryBackendBaseUrl) ? String(secondaryBackendBaseUrl) : String(primaryBackendBaseUrl);
  if (postSensorDataTo(fallback, temperature, humidity)) {
    activeBackend = fallback;
    Serial.print("Switched active backend to: ");
    Serial.println(activeBackend);
    return true;
  }

  return false;
}

String getAlertStatusFrom(const String& baseUrl) {
  HTTPClient http;
  String alertUrl = makeUrl(baseUrl, "/get-alert");

  http.begin(alertUrl);
  int code = http.GET();
  String response = http.getString();
  http.end();

  Serial.print("GET /get-alert [");
  Serial.print(baseUrl);
  Serial.print("] code: ");
  Serial.println(code);
  Serial.print("GET /get-alert response: ");
  Serial.println(response);

  if (!isHttpOk(code)) {
    return "offline";
  }

  // Backend returns JSON like: {"status":"attack|normal|offline", ...}
  if (response.indexOf("\"status\":\"attack\"") >= 0) {
    return "attack";
  }
  if (response.indexOf("\"status\":\"normal\"") >= 0) {
    return "normal";
  }
  return "offline";
}

String getAlertStatus() {
  String status = getAlertStatusFrom(activeBackend);
  if (status != "offline") {
    return status;
  }

  String fallback = (activeBackend == primaryBackendBaseUrl) ? String(secondaryBackendBaseUrl) : String(primaryBackendBaseUrl);
  status = getAlertStatusFrom(fallback);
  if (status != "offline") {
    activeBackend = fallback;
    Serial.print("Switched active backend to: ");
    Serial.println(activeBackend);
  }
  return status;
}

void applyAlertToBuzzer(const String& status) {
  if (status == "attack") {
    digitalWrite(BUZZER_PIN, HIGH);
    Serial.println("ALERT: ATTACK DETECTED");
  } else {
    digitalWrite(BUZZER_PIN, LOW);
    if (status == "normal") {
      Serial.println("System normal");
    } else {
      Serial.println("Alert service offline/unknown");
    }
  }
}

void setup() {
  Serial.begin(115200);
  pinMode(BUZZER_PIN, OUTPUT);
  digitalWrite(BUZZER_PIN, LOW);

  dht.begin();
  connectWiFi();
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("WiFi disconnected. Reconnecting...");
    connectWiFi();
  }

  unsigned long now = millis();
  if (now - lastPublishMs < publishIntervalMs) {
    delay(100);
    return;
  }
  lastPublishMs = now;

  float temperature = dht.readTemperature();
  float humidity = dht.readHumidity();

  if (isnan(temperature) || isnan(humidity)) {
    Serial.println("Failed to read from DHT11");
    return;
  }

  Serial.print("Temp: ");
  Serial.print(temperature);
  Serial.print(" C | Hum: ");
  Serial.print(humidity);
  Serial.println(" %");

  bool posted = postSensorData(temperature, humidity);
  if (!posted) {
    digitalWrite(BUZZER_PIN, LOW);
    Serial.println("Could not publish sensor data");
    return;
  }

  String status = getAlertStatus();
  applyAlertToBuzzer(status);
}
