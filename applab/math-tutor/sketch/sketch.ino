#include <Arduino_RouterBridge.h>
#include <Arduino_LED_Matrix.h>
#include <vector>
#include <cstring>

Arduino_LED_Matrix matrix;
constexpr size_t kFrameSize = 8 * 13;
uint8_t frame[kFrameSize] = {0};

// Frame.to_board_bytes() sends 104 brightness values, one per LED.
void draw(std::vector<uint8_t> nextFrame) {
  if (nextFrame.size() != kFrameSize) {
    return;  // Keep the last valid image if a Bridge message is incomplete.
  }
  memcpy(frame, nextFrame.data(), kFrameSize);
}

void setup() {
  matrix.begin();
  matrix.setGrayscaleBits(3);
  matrix.clear();
  Bridge.begin();
  Bridge.provide("draw", draw);
}

void loop() {
  matrix.draw(frame);
  delay(10);
}
