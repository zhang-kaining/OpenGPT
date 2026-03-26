import { computed, ref } from 'vue'
import { setCurrentUserAvatar } from './useAuth'

const AVATAR_KEY = 'mygpt-user-avatar'

function emojiAvatar(emoji: string, bg: string) {
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="96" height="96" viewBox="0 0 96 96"><rect width="96" height="96" rx="48" fill="${bg}"/><text x="48" y="74" text-anchor="middle" font-size="74">${emoji}</text></svg>`
  return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`
}

const PRESET_AVATARS = [
  '/hamster.svg',
  emojiAvatar('🐻', '#f3e8d3'),
  emojiAvatar('🐱', '#e5eefc'),
  emojiAvatar('🦊', '#ffe8d8'),
]

const avatarRaw = ref<string>(localStorage.getItem(AVATAR_KEY) || PRESET_AVATARS[0])

export const avatarPresets = PRESET_AVATARS

export const userAvatar = computed(() => avatarRaw.value || PRESET_AVATARS[0])

export function setUserAvatar(src: string) {
  avatarRaw.value = src
  localStorage.setItem(AVATAR_KEY, src)
  setCurrentUserAvatar(src)
}

export function uploadUserAvatar(file: File): Promise<void> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => {
      const result = String(reader.result || '')
      if (!result.startsWith('data:image/')) {
        reject(new Error('仅支持图片文件'))
        return
      }
      setUserAvatar(result)
      resolve()
    }
    reader.onerror = () => reject(new Error('头像读取失败'))
    reader.readAsDataURL(file)
  })
}
