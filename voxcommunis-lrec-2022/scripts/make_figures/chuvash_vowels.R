require(tidyverse)
require(ggthemes)
require(ggforce)

chuvash <- read_delim("./data/formants_narrow/chuvash_avg_formants.tsv", delim = "\t", escape_double = FALSE, trim_ws = TRUE)

chuvash_orig <- chuvash
chuvash <- subset(chuvash, V_count_spkr > 5)

vowel_stats <- chuvash %>% group_by(vowel) %>% summarise(grandmeanf1 = mean(mean_f1), sdf1 = sd(mean_f1), grandmeanf2 = mean(mean_f2), sdf2 = sd(mean_f2))

chuvash <- left_join(chuvash, vowel_stats, by = "vowel")

ggplot(chuvash) + geom_point(aes(x = mean_f2, y = mean_f1, color = vowel, shape = setting), alpha= 0.5, size = 4) +
  geom_ellipse(aes(x0 = grandmeanf2, y0 = grandmeanf1, a = sdf2, b = sdf1, angle = 0)) + 
  geom_label(aes(x = grandmeanf2, y = grandmeanf1, label = vowel), size = 12) + 
  scale_x_reverse(limits = c(2700, 800), position = "top") + scale_y_reverse(limits = c(850, 250), position = "right") +
  xlab("mean F2 (Hz)") + ylab("mean F1 (Hz)") +
  annotate("text", label = "Chuvash", x = 2550, y = 850, size = 9) +
  scale_color_viridis_d(end = 0.9) + 
  theme_few(24) + 
  guides(color = "none", label = "none") +
  theme(legend.position=c(0.9,0.1))
ggsave("~/Desktop/chuvash_vowels.png", plot = last_plot(), dpi = 300, units = "in", height = 10, width = 10)

