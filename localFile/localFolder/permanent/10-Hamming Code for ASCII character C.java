import java.util.Scanner;

public class Main {
	public static void main(String[] args) {
		Scanner sc = new Scanner(System.in);

		// 1. Input ASCII Character
		System.out.print("Enter an ASCII character: ");
		char input = sc.next().charAt(0);

		// Extract lower 4 bits (nibble)
		String fullBinary = String.format("%8s", Integer.toBinaryString(input)).replace(' ', '0');
		String nibble = fullBinary.substring(4, 8);

		int[] d = new int[5];
		for (int i = 0; i < 4; i++) d[i + 1] = nibble.charAt(i) - '0';

		// 2. Generate Hamming Code
		int[] h = new int[8];
		h[3] = d[1];
		h[5] = d[2];
		h[6] = d[3];
		h[7] = d[4];
		h[1] = h[3] ^ h[5] ^ h[7];
		h[2] = h[3] ^ h[6] ^ h[7];
		h[4] = h[5] ^ h[6] ^ h[7];

		System.out.print("Generated Hamming Code: ");
		for (int i = 1; i <= 7; i++) System.out.print(h[i]);
		System.out.println("\n-------------------------------------------");

		// 3. Manual Input (This is where you introduce an error)
		System.out.print("Type the 7 bits you received: ");
		String receivedStr = sc.next();

		int[] r = new int[8];
		for (int i = 0; i < 7; i++) {
			r[i + 1] = receivedStr.charAt(i) - '0';
		}

		// 4. Detection & Correction logic on the MANUALLY entered bits
		int s1 = r[1] ^ r[3] ^ r[5] ^ r[7];
		int s2 = r[2] ^ r[3] ^ r[6] ^ r[7];
		int s3 = r[4] ^ r[5] ^ r[6] ^ r[7];

		int errorLoc = (s3 * 4) + (s2 * 2) + s1;

		if (errorLoc == 0) {
			System.out.println("Result: No error detected. Data is perfect.");
		} else {
			System.out.println("Result: Error detected at bit position " + errorLoc);
			r[errorLoc] ^= 1; // Correction

			System.out.print("Corrected Bits: ");
			for (int i = 1; i <= 7; i++) System.out.print(r[i]);
			System.out.println();

			System.out.println("Original Data: " + r[3] + r[5] + r[6] + r[7]);
		}
		sc.close();
	}
}