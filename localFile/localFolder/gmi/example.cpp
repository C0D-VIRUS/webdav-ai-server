#include <stdio.h>
#include <string.h>
#include <stdlib.h>

void encodeHamming(int data[4], int codeword[7]) {
    codeword[2] = data[0];
    codeword[4] = data[1];
    codeword[5] = data[2];
    codeword[6] = data[3];

    codeword[0] = codeword[2] ^ codeword[4] ^ codeword[6];
    codeword[1] = codeword[2] ^ codeword[5] ^ codeword[6];
    codeword[3] = codeword[4] ^ codeword[5] ^ codeword[6];
}

void decodeHamming(int receivedCodeword[7], int correctedCodeword[7], int *errorDetected) {
    memcpy(correctedCodeword, receivedCodeword, 7 * sizeof(int));

    int s1 = correctedCodeword[0] ^ correctedCodeword[2] ^ correctedCodeword[4] ^ correctedCodeword[6];
    int s2 = correctedCodeword[1] ^ correctedCodeword[2] ^ correctedCodeword[5] ^ correctedCodeword[6];
    int s3 = correctedCodeword[3] ^ correctedCodeword[4] ^ correctedCodeword[5] ^ correctedCodeword[6];

    int errorPosition = s3 * 4 + s2 * 2 + s1 * 1;

    if (errorPosition != 0) {
        *errorDetected = 1;
        correctedCodeword[errorPosition - 1] = 1 - correctedCodeword[errorPosition - 1];
    } else {
        *errorDetected = 0;
    }
}

void computeCRC(int data[], int dataLen, int generator[], int genLen, int crcResult[]) {
    int polyDegree = genLen - 1;
    int *dividend = (int *)calloc(dataLen + polyDegree, sizeof(int));
    int *tempGen = (int *)calloc(genLen, sizeof(int));
    
    memcpy(dividend, data, dataLen * sizeof(int));
    memcpy(tempGen, generator, genLen, sizeof(int));

    for (int i = 0; i < dataLen; i++) {
        if (dividend[i] == 1) {
            for (int j = 0; j < genLen; j++) {
                dividend[i + j] ^= tempGen[j];
            }
        }
    }

    memcpy(crcResult, dividend + dataLen, polyDegree * sizeof(int));

    free(dividend);
    free(tempGen);
}

int verifyCRC(int receivedData[], int receivedDataLen, int generator[], int genLen) {
    int polyDegree = genLen - 1;
    int *tempReceived = (int *)calloc(receivedDataLen, sizeof(int));
    int *tempGen = (int *)calloc(genLen, sizeof(int));

    memcpy(tempReceived, receivedData, receivedDataLen * sizeof(int));
    memcpy(tempGen, generator, genLen * sizeof(int));

    for (int i = 0; i < receivedDataLen - polyDegree; i++) {
        if (tempReceived[i] == 1) {
            for (int j = 0; j < genLen; j++) {
                tempReceived[i + j] ^= tempGen[j];
            }
        }
    }

    for (int i = 0; i < polyDegree; i++) {
        if (tempReceived[receivedDataLen - polyDegree + i] == 1) {
            free(tempReceived);
            free(tempGen);
            return 0;
        }
    }

    free(tempReceived);
    free(tempGen);
    return 1;
}

int main() {
    printf("--- Hamming Code (7,4) Demonstration ---\n");

    int data[4] = {1, 0, 1, 1};
    int encoded[7];
    int received[7];
    int corrected[7];
    int errorDetected;

    encodeHamming(data, encoded);

    printf("Original Data: ");
    for (int i = 0; i < 4; i++) printf("%d", data[i]);
    printf("\n");

    printf("Encoded Codeword: ");
    for (int i = 0; i < 7; i++) printf("%d", encoded[i]);
    printf("\n");

    printf("\n--- Scenario 1: No error ---\n");
    memcpy(received, encoded, 7 * sizeof(int));
    printf("Received Codeword (no error): ");
    for (int i = 0; i < 7; i++) printf("%d", received[i]);
    printf("\n");

    decodeHamming(received, corrected, &errorDetected);
    printf("Error Detected: %s\n", errorDetected ? "Yes" : "No");
    if (errorDetected) {
        printf("Corrected Codeword: ");
        for (int i = 0; i < 7; i++) printf("%d", corrected[i]);
        printf("\n");
    } else {
        printf("No correction needed.\n");
    }

    printf("\n--- Scenario 2: Single bit error at position 3 (index 2) ---\n");
    memcpy(received, encoded, 7 * sizeof(int));
    received[2] = 1 - received[2];
    printf("Received Codeword (with error): ");
    for (int i = 0; i < 7; i++) printf("%d", received[i]);
    printf("\n");

    decodeHamming(received, corrected, &errorDetected);
    printf("Error Detected: %s\n", errorDetected ? "Yes" : "No");
    if (errorDetected) {
        printf("Corrected Codeword: ");
        for (int i = 0; i < 7; i++) printf("%d", corrected[i]);
        printf("\n");
        printf("Original (decoded from corrected): ");
        printf("%d%d%d%d\n", corrected[2], corrected[4], corrected[5], corrected[6]);
    }


    printf("\n--- CRC (Cyclic Redundancy Check) Demonstration ---\n");

    int crcData[] = {1, 1, 0, 1, 0, 1, 1, 1};
    int crcDataLen = 8;
    int generator[] = {1, 0, 1, 1};
    int genLen = 4;
    int polyDegree = genLen - 1;

    int *crcResult = (int *)calloc(polyDegree, sizeof(int));
    int *transmittedData = (int *)calloc(crcDataLen + polyDegree, sizeof(int));
    int *receivedCrcData = (int *)calloc(crcDataLen + polyDegree, sizeof(int));

    printf("Original Data: ");
    for (int i = 0; i < crcDataLen; i++) printf("%d", crcData[i]);
    printf("\n");

    computeCRC(crcData, crcDataLen, generator, genLen, crcResult);

    printf("Generated CRC: ");
    for (int i = 0; i < polyDegree; i++) printf("%d", crcResult[i]);
    printf("\n");

    memcpy(transmittedData, crcData, crcDataLen * sizeof(int));
    memcpy(transmittedData + crcDataLen, crcResult, polyDegree * sizeof(int));

    printf("Transmitted Data (Data + CRC): ");
    for (int i = 0; i < crcDataLen + polyDegree; i++) printf("%d", transmittedData[i]);
    printf("\n");

    printf("\n--- Scenario 1: CRC Verification (No Error) ---\n");
    memcpy(receivedCrcData, transmittedData, (crcDataLen + polyDegree) * sizeof(int));
    if (verifyCRC(receivedCrcData, crcDataLen + polyDegree, generator, genLen)) {
        printf("CRC Check: PASS (No error detected)\n");
    } else {
        printf("CRC Check: FAIL (Error detected)\n");
    }

    printf("\n--- Scenario 2: CRC Verification (With Error) ---\n");
    memcpy(receivedCrcData, transmittedData, (crcDataLen + polyDegree) * sizeof(int));
    receivedCrcData[3] = 1 - receivedCrcData[3];
    printf("Received Data (with error): ");
    for (int i = 0; i < crcDataLen + polyDegree; i++) printf("%d", receivedCrcData[i]);
    printf("\n");

    if (verifyCRC(receivedCrcData, crcDataLen + polyDegree, generator, genLen)) {
        printf("CRC Check: PASS (No error detected - this indicates a missed error due to specific error pattern)\n");
    } else {
        printf("CRC Check: FAIL (Error detected)\n");
    }

    free(crcResult);
    free(transmittedData);
    free(receivedCrcData);

    return 0;
}

Possible Viva Questions:

1.  What is the primary goal of error detection and error correction codes?
2.  Explain the basic principle of Hamming codes.
3.  What does the notation (n, k) signify in Hamming codes, e.g., (7,4) Hamming code?
4.  How many bits can a (7,4) Hamming code correct? Can it detect more errors than it can correct?
5.  Describe how parity bits are calculated and used for error detection and correction in Hamming code.
6.  What is a syndrome in the context of Hamming code? How is it used to locate an error?
7.  What is the main limitation of Hamming codes?
8.  What does CRC stand for, and what is its main application?
9.  How does CRC use polynomial division to generate a checksum?
10. What is a generator polynomial in CRC, and why is its selection important?
11. Explain the process of CRC calculation and verification.
12. Why are CRCs generally more effective than simple parity checks for detecting burst errors?
13. Can CRC correct errors? If not, what would be needed to enable error correction with CRC?
14. Give examples of real-world applications where Hamming codes and CRCs are used.
15. What is the fundamental difference in the goals of Hamming codes versus CRCs (correction vs. detection)?