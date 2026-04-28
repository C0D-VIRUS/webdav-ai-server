import java.util.Scanner;

public class Main {
    public static void main(String[] args) {
        Scanner sc = new Scanner(System.in);

        // 1. Input ASCII Character
        System.out.print("Enter an ASCII character: ");
        char input = sc.next().charAt(0);
        
        // Convert to 8-bit binary
        String data = String.format("%8s", Integer.toBinaryString(input)).replace(' ', '0');
        String divisor = "1011"; // Polynomial x^3 + x + 1
        
        // 2. Generate CRC Codeword
        // Append 3 zeros (degree of polynomial)
        String augmentedData = data + "000";
        String remainder = calculateCRC(augmentedData, divisor);
        String codeword = data + remainder;

        System.out.println("Original Data (8-bit): " + data);
        System.out.println("CRC Remainder (3-bit): " + remainder);
        System.out.print("Generated Codeword:    " + codeword);
        System.out.println("\n-------------------------------------------");

        // 3. Manual Input (Introduce an error here)
        System.out.print("Type the 11 bits you received: ");
        String received = sc.next();
        
        // 4. Verification logic
        String checkRemainder = calculateCRC(received, divisor);
        
        // If remainder is all 0s, no error
        if (checkRemainder.equals("000")) {
            System.out.println("Result: No Error Detected. The data is valid.");
        } else {
            System.out.println("Result: Error Detected! (Remainder: " + checkRemainder + ")");
            System.out.println("The received data is corrupted.");
        }
        sc.close();
    }

    // Standard XOR division (Modulo-2)
    static String calculateCRC(String data, String divisor) {
        int[] msg = new int[data.length()];
        int[] div = new int[divisor.length()];

        for (int i = 0; i < data.length(); i++) msg[i] = data.charAt(i) - '0';
        for (int i = 0; i < divisor.length(); i++) div[i] = divisor.charAt(i) - '0';

        for (int i = 0; i <= data.length() - divisor.length(); i++) {
            if (msg[i] == 1) {
                for (int j = 0; j < divisor.length(); j++) {
                    msg[i + j] ^= div[j]; 
                }
            }
        }

        StringBuilder rem = new StringBuilder();
        // The remainder is the last (divisor.length - 1) bits
        for (int i = data.length() - divisor.length() + 1; i < data.length(); i++) {
            rem.append(msg[i]);
        }
        return rem.toString();
    }
}