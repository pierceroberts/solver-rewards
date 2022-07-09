import unittest

from duneapi.types import Address

from src.fetch.period_slippage import SolverSlippage
from src.fetch.transfer_file import TokenType, Transfer, consolidate_transfers
from src.models import AccountingPeriod
from tests.queries.test_internal_trades import TransferType

ONE_ADDRESS = Address("0x1111111111111111111111111111111111111111")
TWO_ADDRESS = Address("0x2222222222222222222222222222222222222222")
ONE_ETH = 10**18


class TestTransferType(unittest.TestCase):
    def setUp(self) -> None:
        self.in_user_upper = "IN_USER"
        self.in_amm_lower = "in_amm"
        self.out_user_mixed = "Out_User"
        self.invalid_type = "invalid"

    def test_valid(self):
        self.assertEqual(
            TransferType.from_str(self.in_user_upper), TransferType.IN_USER
        )
        self.assertEqual(TransferType.from_str(self.in_amm_lower), TransferType.IN_AMM)
        self.assertEqual(
            TransferType.from_str(self.out_user_mixed), TransferType.OUT_USER
        )

    def test_invalid(self):
        with self.assertRaises(ValueError) as err:
            TransferType.from_str(self.invalid_type)
        self.assertEqual(str(err.exception), f"No TransferType {self.invalid_type}!")


class TestTransfer(unittest.TestCase):
    def test_add_slippage(self):
        solver = Address.zero()
        transfer = Transfer(
            token_type=TokenType.NATIVE,
            token_address=None,
            receiver=solver,
            amount_wei=ONE_ETH,
        )
        positive_slippage = SolverSlippage(
            solver_name="Test Solver", solver_address=solver, amount_wei=ONE_ETH // 2
        )
        negative_slippage = SolverSlippage(
            solver_name="Test Solver",
            solver_address=solver,
            amount_wei=-ONE_ETH // 2,
        )
        transfer.add_slippage(positive_slippage)
        self.assertAlmostEqual(transfer.amount, 1.5, delta=0.0000000001)
        transfer.add_slippage(negative_slippage)
        self.assertAlmostEqual(transfer.amount, 1.0, delta=0.0000000001)

        overdraft_slippage = SolverSlippage(
            solver_name="Test Solver", solver_address=solver, amount_wei=-2 * ONE_ETH
        )

        with self.assertRaises(ValueError) as err:
            transfer.add_slippage(overdraft_slippage)
        self.assertEqual(
            str(err.exception),
            f"Invalid adjustment {transfer} "
            f"by {overdraft_slippage.amount_wei / 10**18}",
        )

    def test_merge(self):
        receiver = Address.zero()
        # Native Transfer Merge
        native_transfer1 = Transfer(
            token_type=TokenType.NATIVE,
            token_address=None,
            receiver=receiver,
            amount_wei=ONE_ETH,
        )
        native_transfer2 = Transfer(
            token_type=TokenType.NATIVE,
            token_address=None,
            receiver=receiver,
            amount_wei=ONE_ETH,
        )
        self.assertEqual(
            native_transfer1.merge(native_transfer2),
            Transfer(
                token_type=TokenType.NATIVE,
                token_address=None,
                receiver=receiver,
                amount_wei=2 * ONE_ETH,
            ),
        )
        token = ONE_ADDRESS
        # ERC20 Transfer Merge
        erc20_transfer1 = Transfer(
            token_type=TokenType.ERC20,
            token_address=token,
            receiver=receiver,
            amount_wei=ONE_ETH,
        )
        erc20_transfer2 = Transfer(
            token_type=TokenType.ERC20,
            token_address=token,
            receiver=receiver,
            amount_wei=ONE_ETH,
        )
        self.assertEqual(
            erc20_transfer1.merge(erc20_transfer2),
            Transfer(
                token_type=TokenType.ERC20,
                token_address=token,
                receiver=receiver,
                amount_wei=2 * ONE_ETH,
            ),
        )

        with self.assertRaises(ValueError) as err:
            native_transfer1.merge(erc20_transfer1)
        self.assertEqual(
            f"Can't merge tokens {native_transfer1}, {erc20_transfer1}. "
            f"Requirements met [True, False, False]",
            str(err.exception),
        )

        with self.assertRaises(ValueError) as err:
            # Different recipients
            t1 = Transfer(
                token_type=TokenType.ERC20,
                token_address=token,
                receiver=ONE_ADDRESS,
                amount_wei=2 * ONE_ETH,
            )
            t2 = Transfer(
                token_type=TokenType.ERC20,
                token_address=token,
                receiver=TWO_ADDRESS,
                amount_wei=2 * ONE_ETH,
            )
            t1.merge(t2)
        self.assertEqual(
            f"Can't merge tokens {t1}, {t2}. Requirements met [False, True, True]",
            str(err.exception),
        )

        with self.assertRaises(ValueError) as err:
            # Different Token Addresses
            t1 = Transfer(
                token_type=TokenType.ERC20,
                token_address=ONE_ADDRESS,
                receiver=receiver,
                amount_wei=2 * ONE_ETH,
            )
            t2 = Transfer(
                token_type=TokenType.ERC20,
                token_address=TWO_ADDRESS,
                receiver=receiver,
                amount_wei=2 * ONE_ETH,
            )
            t1.merge(t2)
        self.assertEqual(
            f"Can't merge tokens {t1}, {t2}. Requirements met [True, True, False]",
            str(err.exception),
        )

    def test_consolidation(self):
        recipients = [
            Address.from_int(0),
            Address.from_int(1),
        ]
        tokens = [
            Address.from_int(2),
            Address.from_int(3),
        ]
        transfer_list = [
            Transfer(
                token_type=TokenType.ERC20,
                token_address=tokens[0],
                receiver=recipients[0],
                amount_wei=1 * ONE_ETH,
            ),
            Transfer(
                token_type=TokenType.ERC20,
                token_address=tokens[0],
                receiver=recipients[0],
                amount_wei=2 * ONE_ETH,
            ),
            Transfer(
                token_type=TokenType.ERC20,
                token_address=tokens[1],
                receiver=recipients[0],
                amount_wei=3 * ONE_ETH,
            ),
            Transfer(
                token_type=TokenType.ERC20,
                token_address=tokens[0],
                receiver=recipients[1],
                amount_wei=4 * ONE_ETH,
            ),
            Transfer(
                token_type=TokenType.NATIVE,
                token_address=None,
                receiver=recipients[0],
                amount_wei=5 * ONE_ETH,
            ),
            Transfer(
                token_type=TokenType.NATIVE,
                token_address=None,
                receiver=recipients[0],
                amount_wei=6 * ONE_ETH,
            ),
            Transfer(
                token_type=TokenType.NATIVE,
                token_address=None,
                receiver=recipients[1],
                amount_wei=7 * ONE_ETH,
            ),
            Transfer(
                token_type=TokenType.NATIVE,
                token_address=None,
                receiver=recipients[1],
                amount_wei=8 * ONE_ETH,
            ),
        ]

        expected = [
            Transfer(
                token_type=TokenType.NATIVE,
                token_address=None,
                receiver=recipients[1],
                amount_wei=15 * ONE_ETH,
            ),
            Transfer(
                token_type=TokenType.NATIVE,
                token_address=None,
                receiver=recipients[0],
                amount_wei=11 * ONE_ETH,
            ),
            Transfer(
                token_type=TokenType.ERC20,
                token_address=tokens[0],
                receiver=recipients[1],
                amount_wei=4 * ONE_ETH,
            ),
            Transfer(
                token_type=TokenType.ERC20,
                token_address=tokens[0],
                receiver=recipients[0],
                amount_wei=3 * ONE_ETH,
            ),
            Transfer(
                token_type=TokenType.ERC20,
                token_address=tokens[1],
                receiver=recipients[0],
                amount_wei=3 * ONE_ETH,
            ),
        ]
        self.assertEqual(expected, consolidate_transfers(transfer_list))

    def test_receiver_error(self):
        transfer = Transfer(
            token_type=TokenType.NATIVE,
            token_address=None,
            receiver=ONE_ADDRESS,
            amount_wei=1 * ONE_ETH,
        )
        with self.assertRaises(AssertionError) as err:
            transfer.add_slippage(
                SolverSlippage(
                    solver_name="Test Solver", solver_address=TWO_ADDRESS, amount_wei=0
                )
            )
            self.assertEqual(err, "receiver != solver")

    def test_from_dict(self):
        self.assertEqual(
            Transfer.from_dict(
                {
                    "token_type": "native",
                    "token_address": None,
                    "receiver": ONE_ADDRESS.address,
                    "amount": "1234000000000000000",
                }
            ),
            Transfer(
                token_type=TokenType.NATIVE,
                token_address=None,
                receiver=ONE_ADDRESS,
                amount_wei=1234 * 10**15,
            ),
        )

        with self.assertRaises(ValueError) as err:
            Transfer.from_dict(
                {
                    "token_type": "erc20",
                    "token_address": None,
                    "receiver": ONE_ADDRESS.address,
                    "amount": "1000000000000000000",
                }
            )
        self.assertEqual(
            str(err.exception), "ERC20 transfers must have valid token_address"
        )
        with self.assertRaises(ValueError) as err:
            Transfer.from_dict(
                {
                    "token_type": "native",
                    "token_address": ONE_ADDRESS.address,
                    "receiver": ONE_ADDRESS.address,
                    "amount": "1000000000000000000",
                }
            )
        self.assertEqual(
            str(err.exception), "Native transfers must have null token_address"
        )


class TestAccountingPeriod(unittest.TestCase):
    def test_str(self):
        self.assertEqual(
            "2022-01-01-to-2022-01-08", str(AccountingPeriod("2022-01-01"))
        )
        self.assertEqual(
            "2022-01-01-to-2022-01-07", str(AccountingPeriod("2022-01-01", 6))
        )

    def test_invalid(self):
        bad_date_string = "Invalid date string"
        with self.assertRaises(ValueError) as err:
            AccountingPeriod(bad_date_string)

        self.assertEqual(
            f"time data '{bad_date_string}' does not match format '%Y-%m-%d'",
            str(err.exception),
        )


if __name__ == "__main__":
    unittest.main()
