// This #include statement was automatically added by the Particle IDE.
#include "lib1.h"

// This #include statement was automatically added by the Particle IDE.
#include <HttpClient.h>

// Include Particle Device OS APIs
#include "Particle.h"

#include <Grove_LCD_RGB_Backlight.h>

rgb_lcd lcd;


SYSTEM_THREAD(ENABLED);
// Let Device OS manage the connection to the Particle Cloud
SYSTEM_MODE(AUTOMATIC);



HttpClient http;
http_header_t headers[] = {
    { "Content-Type", "application/x-www-form-urlencoded" },
    { NULL, NULL } // end marker
};

http_request_t request;
request.hostname = "raspberrypi.local";
request.port = 8000;
request.path = "/blow-status";

http_response_t response;

// Show system, cloud connectivity, and application logs over USB
// View logs with CLI using 'particle serial monitor --follow'
SerialLogHandler logHandler(LOG_LEVEL_INFO);

// setup() runs once, when the device is first turned on
void setup() {
    // Open a serial connection to print data back to your computer
    Serial.begin(9600);
}

void loop() {
    
    http.get(request, response, headers);
    
    Serial.print("HTTP Response: ");
    Serial.println(response.body);
    
    if (response.body == "READY"){
        //initialize by putting the animation on the screen
        lcd.print("GET READY TO BLOW JOE.")
        sleep(3)
        lcd.print("you will blow for around 10 seconds, as hard as you can")
        sleep(3)
        lcd.print("3")
        sleep(1)
        lcd.print("2")
        sleep(1)
        lcd.print("1")
        sleep(1)
        lcd.print("TAKE A DEEEEP BREATH AND.... BLOW!")
    }
    
    int sensorValue = analogRead(A0);  // Raw reading (0–4095)
    float voltage = sensorValue * (5.0 / 4095.0);  // Convert to volts

    // Create a message string with both values
    char msg[64];
    snprintf(msg, sizeof(msg), "Raw: %d | V: %.2f", sensorValue, voltage);

    // Publish it to the Particle cloud
    Particle.publish("alcohol_reading", msg, PRIVATE);

    // Wait 5 seconds between updates (1/sec will hit rate limit)
    delay(5000);
}

