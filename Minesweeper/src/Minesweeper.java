//
// Source code recreated from a .class file by IntelliJ IDEA
// (powered by FernFlower decompiler)
//

import java.util.Scanner;

public class Minesweeper {
    char[][] board;
    private Minesweeper.GameState gameState;
    private int numHidden;

    public Minesweeper() {
        this.gameState = Minesweeper.GameState.NOTENDED;
    }

    public void initialize(int rows, int cols, int numMines) {
        this.board = new char[rows][cols];

        int row;
        int mineLocation;
        for(row = 0; row < rows; ++row) {
            for(mineLocation = 0; mineLocation < cols; ++mineLocation) {
                this.board[row][mineLocation] = 'H';
            }
        }

        row = 0;

        while(row < numMines) {
            mineLocation = (int)(Math.random() * (double)rows * (double)cols);
            int row = mineLocation / cols;
            int col = mineLocation % cols;
            if (this.board[row][col] != '*') {
                this.board[row][col] = '*';
                ++row;
            }
        }

        this.numHidden = rows * cols - numMines;
    }

    public void print() {
        System.out.println();

        for(int row = 0; row < this.board.length; ++row) {
            for(int col = 0; col < this.board[0].length; ++col) {
                if (this.board[row][col] == '*' && this.gameState.equals(Minesweeper.GameState.NOTENDED)) {
                    System.out.print('H');
                } else {
                    System.out.print(this.board[row][col]);
                }

                System.out.print(" ");
            }

            System.out.println();
        }

    }

    public void nextMove(int row, int col) {
        if (row >= 0 && row < this.board.length && col >= 0 && col < this.board[0].length) {
            if (this.board[row][col] == '*') {
                this.gameState = Minesweeper.GameState.LOSE;
            }

            if (this.board[row][col] == 'H') {
                int numNeighbors = this.getNeighboringMineCount(row, col);
                if (numNeighbors == 0) {
                    this.mark(row, col, '.');

                    // TODO Potentially refactor this code with the code in getNeighboringMineCount
                    for(int rowOffset = -1; rowOffset <= 1; ++rowOffset) {
                        for(int colOffset = -1; colOffset <= 1; ++colOffset) {
                            int currRow = row + rowOffset;
                            int currCol = col + colOffset;
                            if (currRow >= 0 && currRow < this.board.length && currCol >= 0 && currCol < this.board[0].length) {
                                this.nextMove(currRow, currCol);
                            }
                        }
                    }
                } else {
                    this.mark(row, col, (char)(48 + numNeighbors));
                }

            }
        }
    }

    public Minesweeper.GameState getGameState() {
        return this.gameState;
    }

    private int getNeighboringMineCount(int row, int col) {
        int ret = 0;

        for(int rowOffset = -1; rowOffset <= 1; ++rowOffset) {
            for(int colOffset = -1; colOffset <= 1; ++colOffset) {
                int currRow = row + rowOffset;
                int currCol = col + colOffset;
                if (currRow >= 0 && currRow < this.board.length && currCol >= 0 && currCol < this.board[0].length && this.board[currRow][currCol] == '*') {
                    ++ret;
                }
            }
        }

        return ret;
    }

    private void mark(int row, int col, char state) {
        this.board[row][col] = state;
        --this.numHidden;
        if (this.numHidden == 0) {
            this.gameState = Minesweeper.GameState.WIN;
        }

    }

    public static void main(String[] args) {
        Minesweeper ms = new Minesweeper();
        ms.initialize(Integer.parseInt(args[0]), Integer.parseInt(args[1]), Integer.parseInt(args[2]));
        ms.print();
        Scanner scanner = new Scanner(System.in);

        while(ms.getGameState().equals(Minesweeper.GameState.NOTENDED)) {
            System.out.println("Row: ");
            int row = scanner.nextInt();
            System.out.println("Col: ");
            int col = scanner.nextInt();
            ms.nextMove(row, col);
            ms.print();
        }

        System.out.println("You " + ms.getGameState().toString());
    }

    static enum GameState {
        NOTENDED,
        WIN,
        LOSE;

        private GameState() {
        }
    }
}
