# Makefile for esort (external merge sort)
#
#   make        編譯出 esort
#   make clean  移除編譯產物

CC      = gcc
CFLAGS  = -Wall -Wextra -O2 -std=c11
LDFLAGS =
TARGET  = esort
OBJS    = esort.o

.PHONY: all clean

all: $(TARGET)

$(TARGET): $(OBJS)
	$(CC) $(CFLAGS) -o $@ $(OBJS) $(LDFLAGS)

%.o: %.c
	$(CC) $(CFLAGS) -c -o $@ $<

clean:
	rm -f $(TARGET) $(OBJS)