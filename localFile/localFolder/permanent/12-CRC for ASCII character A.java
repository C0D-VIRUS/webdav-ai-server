import java.util.Scanner;

public class Main {
    public static void main(String[] args) {
        Scanner sc = new Scanner(System.in);

        // 1. Input ASCII Character
        System.out.print("Enter an ASCII character (e.g., A): ");
        char input = sc.next().charAt(0);
        
        // Convert to 8-bit binary
        String data = String.format("%8s", Integer.toBinaryString(input)).replace(' ', '0');
        String divisor = "10011"; // Polynomial x^4 + x + 1
        
        // 2. Generate CRC Codeword
        // Append 4 zeros (degree of polynomial is 4)
        String augmentedData = data + "0000";
        String remainder = calculateCRC(augmentedData, divisor);
        String codeword = data + remainder;

        System.out.println("Original Data (8-bit): " + data);
        System.out.println("CRC Remainder (4-bit): " + remainder);
        System.out.print("Generated Codeword:    " + codeword);
        System.out.println("\n-------------------------------------------");

        // 3. Manual Input (This is where you introduce errors)
        System.out.print("Type the 12 bits you received: ");
        String received = sc.next();
        
        // 4. Verification logic
        String checkRemainder = calculateCRC(received, divisor);
        
        // Check if remainder contains any '1's
        if (checkRemainder.equals("0000")) {
            System.out.println("Result: No Error Detected. Data integrity verified.");
        } else {
            System.out.println("Result: Error Detected!");
            System.out.println("Remainder: " + checkRemainder + " (Non-zero means corruption)");
        }
        sc.close();
    }

    // Modulo-2 Division (XOR logic)
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
        // Extract the last 4 bits as the remainder
        for (int i = data.length() - divisor.length() + 1; i < data.length(); i++) {
            rem.append(msg[i]);
        }
        return rem.toString();
    }
}