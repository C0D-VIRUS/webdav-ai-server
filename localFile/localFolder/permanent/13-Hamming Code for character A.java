import java.util.Scanner;

public class Main {
    public static void main(String[] args) {
        Scanner sc = new Scanner(System.in);

        // 1. Data Input
        System.out.print("Enter an ASCII character to transmit (e.g., A): ");
        char input = sc.next().charAt(0);
        
        // Extract lower 4 bits for the (7,4) block
        String fullBinary = String.format("%8s", Integer.toBinaryString(input)).replace(' ', '0');
        String dataBits = fullBinary.substring(4, 8);
        System.out.println("Data to be protected (bits 4-7): " + dataBits);

        int[] d = new int[5];
        for (int i = 0; i < 4; i++) d[i + 1] = dataBits.charAt(i) - '0';

        // 2. Encoding Phase
        int[] h = new int[8];
        h[3] = d[1]; h[5] = d[2]; h[6] = d[3]; h[7] = d[4];

        // Parity bits calculation
        h[1] = h[3] ^ h[5] ^ h[7];
        h[2] = h[3] ^ h[6] ^ h[7];
        h[4] = h[5] ^ h[6] ^ h[7];

        System.out.print("Sent Hamming Code: ");
        for (int i = 1; i <= 7; i++) System.out.print(h[i]);
        System.out.println("\n-------------------------------------------");

        // 3. Noise Simulation (Manual Entry)
        System.out.println("SYSTEM: Noise may corrupt the message during transmission.");
        System.out.print("Enter the 7 bits received at the destination: ");
        String receivedStr = sc.next();
        
        int[] r = new int[8];
        for (int i = 0; i < 7; i++) {
            r[i + 1] = receivedStr.charAt(i) - '0';
        }

        // 4. Integrity Check (Syndrome Calculation)
        int s1 = r[1] ^ r[3] ^ r[5] ^ r[7];
        int s2 = r[2] ^ r[3] ^ r[6] ^ r[7];
        int s3 = r[4] ^ r[5] ^ r[6] ^ r[7];

        int errorLoc = (s3 * 4) + (s2 * 2) + s1;

        if (errorLoc == 0) {
            System.out.println("Integrity Check: Data is consistent. No errors.");
        } else {
            System.out.println("Integrity Check: Noise detected! Corruption at bit " + errorLoc);
            r[errorLoc] ^= 1; // Correcting the bit automatically
            
            System.out.print("System Corrected Bits: ");
            for (int i = 1; i <= 7; i++) System.out.print(r[i]);
            System.out.println();
            
            System.out.println("Recovered Data Nibble: " + r[3] + r[5] + r[6] + r[7]);
        }
        sc.close();
    }
}