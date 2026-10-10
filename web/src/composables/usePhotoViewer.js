import { reactive } from 'vue'
import axios from 'axios'
import { API_BASE } from '../api/base'
import { toast } from './useToast'

/**
 * "Click a photo in a grid -> PhotoViewer" for any page.
 *
 * `listRef` is the ref holding the array the grid renders; the viewer is
 * given that same array, so removing an item from it updates the grid and
 * the viewer together (PhotoViewer clamps its index / closes when empty).
 *
 * onChange(delta) is called with -1 after a trash and +1 after an undo,
 * so pages can adjust counts or invalidate caches.
 *
 * trash(item) is optimistic and undoable, matching the timeline: the photo
 * disappears at once, a toast offers 撤销, and a failed request puts it back.
 *
 * Usage:
 *   const { viewer, openViewer, closeViewer, trashFromViewer } = usePhotoViewer(photos)
 *   <div v-for="(p, i) in photos" @click="openViewer(i)">
 *   <PhotoViewer v-if="viewer.open" :items="photos" :start-index="viewer.index"
 *                @close="closeViewer" @trash="trashFromViewer" />
 */
export function usePhotoViewer(listRef, { onChange } = {}) {
  const viewer = reactive({ open: false, index: 0 })

  const openViewer = (index) => {
    viewer.index = index
    viewer.open = true
  }
  const closeViewer = () => { viewer.open = false }

  const removeLocal = (item) => {
    const i = listRef.value.indexOf(item)
    if (i !== -1) listRef.value.splice(i, 1)
    return i
  }
  const putBack = (item, at) => {
    if (!listRef.value.includes(item)) {
      listRef.value.splice(Math.min(Math.max(at, 0), listRef.value.length), 0, item)
    }
  }

  const trashFromViewer = async (item) => {
    const at = removeLocal(item)
    try {
      await axios.post(`${API_BASE}/files/trash`, { file_paths: [item.file_path] })
      onChange?.(-1)
      toast('已移入回收站', {
        actionLabel: '撤销',
        duration: 6000,
        onAction: async () => {
          try {
            await axios.post(`${API_BASE}/files/restore`, { file_paths: [item.file_path] })
            putBack(item, at)
            onChange?.(+1)
          } catch (e) {
            toast('恢复失败', { type: 'error' })
          }
        },
      })
    } catch (e) {
      putBack(item, at)
      toast('移入回收站失败', { type: 'error' })
    }
  }

  return { viewer, openViewer, closeViewer, trashFromViewer }
}
