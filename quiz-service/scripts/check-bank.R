# Each original question has a small executable semantic check.
bank <- jsonlite::fromJSON('sample-bank.json', simplifyVector = FALSE)
stopifnot(length(bank) == 100L)
for (question in bank) {
  result <- eval(parse(text = question$check), envir = new.env(parent = globalenv()))
  if (!isTRUE(result)) stop(paste('Incorrect answer for', question$code))
}
cat('All 100 R answer checks passed.\n')
