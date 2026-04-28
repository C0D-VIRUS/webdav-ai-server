import java.util.Scanner;

public class Main {
    public static void main(String[] args) {
        Scanner sc = new Scanner(System.in);

        System.out.print("[BANK] Enter 8-bit binary transaction data: ");
        String data = sc.next();
        String divisor = "1101"; 

        // Generate Codeword
        String augmented = data + "000";
        String remainder = calculateCRC(augmented, divisor);
        String codeword = data + remainder;

        System.out.println("[BANK] Generated Codeword to send: " + codeword);
        System.out.println("-------------------------------------------");

        System.out.print("[BANK] Enter bits received at Branch: ");
        String received = sc.next();

        // Verification
        if (calculateCRC(received, divisor).equals("000")) {
            System.out.println("RESULT: Transaction Secure. No Tampering.");
        } else {
            System.out.println("RESULT: CRITICAL ERROR! Data Corrupted.");
        }
        sc.close();
    }

    static String calculateCRC(String data, String divisor) {
        int[] msg = new int[data.length()];
        for (int i = 0; i < data.length(); i++) msg[i] = data.charAt(i) - '0';
        int[] div = new int[divisor.length()];
        for (int i = 0; i < divisor.length(); i++) div[i] = divisor.charAt(i) - '0';

        for (int i = 0; i <= data.length() - divisor.length(); i++) {
            if (msg[i] == 1) {
                for (int j = 0; j < divisor.length(); j++) msg[i + j] ^= div[j];
            }
        }
        StringBuilder rem = new StringBuilder();
        for (int i = data.length() - divisor.length() + 1; i < data.length(); i++) rem.append(msg[i]);
        return rem.toString();
    }
}