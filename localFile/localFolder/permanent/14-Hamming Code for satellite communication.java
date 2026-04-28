import java.util.Scanner;

public class Main {
    public static void main(String[] args) {
        Scanner sc = new Scanner(System.in);

        System.out.print("[SATELLITE] Enter 4-bit binary telemetry: ");
        String binInput = sc.next();
        
        int[] d = new int[5];
        for (int i = 0; i < 4; i++) d[i + 1] = binInput.charAt(i) - '0';

        // Encode Hamming (7,4)
        int[] h = new int[8];
        h[3] = d[1]; h[5] = d[2]; h[6] = d[3]; h[7] = d[4];
        h[1] = h[3] ^ h[5] ^ h[7];
        h[2] = h[3] ^ h[6] ^ h[7];
        h[4] = h[5] ^ h[6] ^ h[7];

        System.out.print("[SATELLITE] Uplink Hamming Code: ");
        for (int i = 1; i <= 7; i++) System.out.print(h[i]);
        System.out.println("\n-------------------------------------------");

        System.out.print("[GROUND STATION] Enter 7 bits received: ");
        String receivedStr = sc.next();
        
        int[] r = new int[8];
        for (int i = 0; i < 7; i++) r[i + 1] = receivedStr.charAt(i) - '0';

        // Syndrome Calculation
        int s1 = r[1] ^ r[3] ^ r[5] ^ r[7];
        int s2 = r[2] ^ r[3] ^ r[6] ^ r[7];
        int s3 = r[4] ^ r[5] ^ r[6] ^ r[7];
        int errorLoc = (s3 * 4) + (s2 * 2) + s1;

        if (errorLoc == 0) {
            System.out.println("RESULT: Signal Clear. Data verified.");
        } else {
            System.out.println("RESULT: Interference detected at bit " + errorLoc);
            r[errorLoc] ^= 1; // Correction
            System.out.print("SATELLITE AUTO-CORRECTED BITS: ");
            for (int i = 1; i <= 7; i++) System.out.print(r[i]);
            System.out.println();
        }
        sc.close();
    }
}