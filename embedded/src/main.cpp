#include <Arduino.h>
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <OneWire.h>
#include <DallasTemperature.h>
#include "env.h"

int pirStat = 0;

OneWire oneWire(temp_sensor);
DallasTemperature sensors(&oneWire);


void post_sensor_data(float temp, bool presence){
  HTTPClient http;
  String requestBody;

  http.begin(endpoint);
  http.addHeader("Content-Type", "application/json");

  JsonDocument doc;

  doc["temp"] = temp;
  doc["presence"] = presence;

  doc.shrinkToFit();

  serializeJson(doc, requestBody);

  int httpResponseCode = http.PUT(requestBody);

  Serial.print("HERE IS THE RESPONSE: ");
  Serial.println(requestBody);
  Serial.println(http.getString());
  Serial.println();

  http.end();
}

void get_fan_data(){
  HTTPClient http;

  String newEndpoint;
  String path = "/fan";
  newEndpoint = endpoint + path;  

  http.begin(newEndpoint);

  int httpResponseCode = http.GET();

  if(httpResponseCode > 0) {
    Serial.print("HTTP Response code: ");
    Serial.println(httpResponseCode);

    String responseBody = http.getString();
    Serial.println(responseBody);

    JsonDocument doc;
    DeserializationError error = deserializeJson(doc, responseBody);

    if (error) {
      Serial.print("deserializeJson() failed: ");
      Serial.println(error.c_str());
      return;
    }

    bool fanStat = doc["fan"];
    digitalWrite(fan_pin, fanStat);
    
  }
  else{
    Serial.print("Error code: ");
    Serial.println(httpResponseCode);
  }
  http.end();
}

void get_light_data(){
  HTTPClient http;

  String newEndpoint;
  String path = "/light";
  newEndpoint = endpoint + path;   

  http.begin(newEndpoint);

  int httpResponseCode = http.GET();

  if(httpResponseCode > 0) {
    Serial.print("HTTP Response code: ");
    Serial.println(httpResponseCode);

    String responseBody = http.getString();
    Serial.println(responseBody);

    JsonDocument doc;
    DeserializationError error = deserializeJson(doc, responseBody);

    if (error) {
      Serial.print("deserializeJson() failed: ");
      Serial.println(error.c_str());
      return;
    }

    bool lightStat = doc["light"];
    digitalWrite(led_pin, lightStat);
  }
  else{
    Serial.print("Error code: ");
    Serial.println(httpResponseCode);
  }
  http.end();
}

void setup() {
  Serial.begin(9600);
	
	
  WiFi.begin(ssid, password);

	
  Serial.println("Connecting");
  while(WiFi.status() != WL_CONNECTED) {
    delay(1000);
    Serial.print(".");
  }
  Serial.println("");
  Serial.print("Connected to WiFi network with IP Address: ");
  Serial.println(WiFi.localIP());

  
  pinMode(fan_pin, OUTPUT);
  pinMode(led_pin, OUTPUT);
  pinMode(pir_pin, INPUT);
}

void loop() {
  
  if(WiFi.status()== WL_CONNECTED){
    
    sensors.requestTemperatures();
    float t = sensors.getTempCByIndex(0);

    
    bool p;
    pirStat = digitalRead(pir_pin);
    if(pirStat == HIGH){
      p = true;
    }else{
      p = false;
    }
    
    post_sensor_data(t, p);
    delay(5000);
    
    get_fan_data();
    get_light_data();
    delay(5000);
  }
  else {
    Serial.println("WiFi Disconnected");
  }
}